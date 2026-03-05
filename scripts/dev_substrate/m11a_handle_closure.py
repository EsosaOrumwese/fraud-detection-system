#!/usr/bin/env python3
"""Build and publish M11.A authority/handle closure artifacts."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


HANDLES_PATH = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_handles(path: Path) -> dict[str, Any]:
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
    s = str(value).strip()
    s_lower = s.lower()
    if s == "":
        return True
    if s_lower in {"tbd", "todo", "none", "null", "unset"}:
        return True
    if "to_pin" in s_lower or "placeholder" in s_lower:
        return True
    if "<" in s and ">" in s:
        return True
    return False


def is_wildcard(value: Any) -> bool:
    s = str(value).strip()
    return s in {"*", "**"} or "*" in s


def s3_get_json(s3_client: Any, bucket: str, key: str) -> dict[str, Any]:
    body = s3_client.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("json_not_object")
    return payload


def s3_put_json(s3_client: Any, bucket: str, key: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8")
    s3_client.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
    s3_client.head_object(Bucket=bucket, Key=key)


def write_local_artifacts(run_dir: Path, artifacts: dict[str, dict[str, Any]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in artifacts.items():
        (run_dir / name).write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def dedupe_blockers(blockers: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for blocker in blockers:
        code = str(blocker.get("code", "")).strip()
        message = str(blocker.get("message", "")).strip()
        sig = (code, message)
        if sig in seen:
            continue
        seen.add(sig)
        out.append({"code": code, "message": message})
    return out


def s3_get_first(
    s3_client: Any,
    bucket: str,
    keys: list[str],
) -> tuple[dict[str, Any] | None, str, str]:
    for key in keys:
        try:
            payload = s3_get_json(s3_client, bucket, key)
            return payload, key, ""
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            last_err = type(exc).__name__
    return None, "", last_err if "last_err" in locals() else "unreadable"


def main() -> int:
    env = dict(os.environ)
    execution_id = env.get("M11A_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M11A_RUN_DIR", "").strip()
    evidence_bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m10_execution = env.get("UPSTREAM_M10_EXECUTION", "").strip()
    upstream_m10j_execution = env.get("UPSTREAM_M10J_EXECUTION", "").strip()
    upstream_m10i_execution = env.get("UPSTREAM_M10I_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M11A_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M11A_RUN_DIR is required.")
    if not evidence_bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m10_execution:
        raise SystemExit("UPSTREAM_M10_EXECUTION is required.")
    if not upstream_m10j_execution:
        raise SystemExit("UPSTREAM_M10J_EXECUTION is required.")
    if not upstream_m10i_execution:
        raise SystemExit("UPSTREAM_M10I_EXECUTION is required.")

    run_dir = Path(run_dir_raw)
    captured_at = now_utc()
    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    m10_summary_keys = [
        f"evidence/dev_full/run_control/{upstream_m10_execution}/m10_execution_summary.json",
        f"evidence/dev_full/run_control/{upstream_m10_execution}/stress/m10_execution_summary.json",
    ]
    m10j_summary_keys = [
        f"evidence/dev_full/run_control/{upstream_m10j_execution}/m10j_execution_summary.json",
        f"evidence/dev_full/run_control/{upstream_m10_execution}/stress/m10j_execution_summary.json",
    ]
    m11_handoff_keys = [
        f"evidence/dev_full/run_control/{upstream_m10i_execution}/m11_handoff_pack.json",
        f"evidence/dev_full/run_control/{upstream_m10_execution}/stress/m11_handoff_pack.json",
    ]

    m10_summary, m10_summary_key, m10_summary_err = s3_get_first(s3, evidence_bucket, m10_summary_keys)
    if m10_summary is None:
        read_errors.append({"surface": "|".join(m10_summary_keys), "error": m10_summary_err})
        blockers.append({"code": "M11-B1", "message": "M10 closure summary unreadable for M11.A entry."})

    m10j_summary, m10j_summary_key, m10j_summary_err = s3_get_first(s3, evidence_bucket, m10j_summary_keys)
    if m10j_summary is None:
        read_errors.append({"surface": "|".join(m10j_summary_keys), "error": m10j_summary_err})
        blockers.append({"code": "M11-B1", "message": "M10.J closure summary unreadable for M11.A entry."})

    m11_handoff, m11_handoff_key, m11_handoff_err = s3_get_first(s3, evidence_bucket, m11_handoff_keys)
    if m11_handoff is None:
        read_errors.append({"surface": "|".join(m11_handoff_keys), "error": m11_handoff_err})
        blockers.append({"code": "M11-B1", "message": "M11 handoff pack unreadable from M10.I."})

    platform_run_id = ""
    scenario_run_id = ""

    if m10_summary is not None:
        if not bool(m10_summary.get("overall_pass")):
            blockers.append({"code": "M11-B1", "message": "M10 summary is not pass posture."})
        if str(m10_summary.get("verdict", "")).strip() != "ADVANCE_TO_M11":
            blockers.append({"code": "M11-B1", "message": "M10 verdict is not ADVANCE_TO_M11."})
        if str(m10_summary.get("next_gate", "")).strip() != "M11_READY":
            blockers.append({"code": "M11-B1", "message": "M10 next_gate is not M11_READY."})
        platform_run_id = str(m10_summary.get("platform_run_id", "")).strip()
        scenario_run_id = str(m10_summary.get("scenario_run_id", "")).strip()

    if m10j_summary is not None:
        if not bool(m10j_summary.get("overall_pass")):
            blockers.append({"code": "M11-B1", "message": "M10.J summary is not pass posture."})
        if str(m10j_summary.get("verdict", "")).strip() != "ADVANCE_TO_M11":
            blockers.append({"code": "M11-B1", "message": "M10.J verdict is not ADVANCE_TO_M11."})
        if str(m10j_summary.get("next_gate", "")).strip() != "M11_READY":
            blockers.append({"code": "M11-B1", "message": "M10.J next_gate is not M11_READY."})

        j_platform = str(m10j_summary.get("platform_run_id", "")).strip()
        j_scenario = str(m10j_summary.get("scenario_run_id", "")).strip()
        if platform_run_id and j_platform and platform_run_id != j_platform:
            blockers.append({"code": "M11-B1", "message": "platform_run_id mismatch between M10 and M10.J summaries."})
        if scenario_run_id and j_scenario and scenario_run_id != j_scenario:
            blockers.append({"code": "M11-B1", "message": "scenario_run_id mismatch between M10 and M10.J summaries."})
        if not platform_run_id:
            platform_run_id = j_platform
        if not scenario_run_id:
            scenario_run_id = j_scenario

    if m11_handoff is not None:
        if not bool(m11_handoff.get("p13_overall_pass")):
            blockers.append({"code": "M11-B1", "message": "M11 handoff p13_overall_pass is false."})
        if str(m11_handoff.get("p13_verdict", "")).strip() != "ADVANCE_TO_P14":
            blockers.append({"code": "M11-B1", "message": "M11 handoff p13_verdict is not ADVANCE_TO_P14."})
        if str(m11_handoff.get("m11_entry_gate", {}).get("next_gate", "")).strip() != "M11_READY":
            blockers.append({"code": "M11-B1", "message": "M11 handoff entry next_gate is not M11_READY."})

        h_platform = str(m11_handoff.get("platform_run_id", "")).strip()
        h_scenario = str(m11_handoff.get("scenario_run_id", "")).strip()
        if platform_run_id and h_platform and platform_run_id != h_platform:
            blockers.append({"code": "M11-B1", "message": "platform_run_id mismatch between M10 closure and M11 handoff."})
        if scenario_run_id and h_scenario and scenario_run_id != h_scenario:
            blockers.append({"code": "M11-B1", "message": "scenario_run_id mismatch between M10 closure and M11 handoff."})
        if not platform_run_id:
            platform_run_id = h_platform
        if not scenario_run_id:
            scenario_run_id = h_scenario

    if not platform_run_id or not scenario_run_id:
        blockers.append({"code": "M11-B1", "message": "Run scope unresolved for M11 entry."})

    required_handles = [
        "S3_EVIDENCE_BUCKET",
        "S3_RUN_CONTROL_ROOT_PATTERN",
        "SM_TRAINING_JOB_NAME_PREFIX",
        "SM_BATCH_TRANSFORM_JOB_NAME_PREFIX",
        "SM_MODEL_PACKAGE_GROUP_NAME",
        "SM_ENDPOINT_NAME",
        "MF_EVAL_REPORT_PATH_PATTERN",
        "MF_CANDIDATE_BUNDLE_PATH_PATTERN",
        "MF_LEAKAGE_PROVENANCE_CHECK_PATH_PATTERN",
        "MLFLOW_HOSTING_MODE",
        "MLFLOW_EXPERIMENT_PATH",
        "PHASE_BUDGET_ENVELOPE_PATH_PATTERN",
        "PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN",
    ]

    missing_handles: list[str] = []
    placeholder_handles: list[str] = []
    wildcard_handles: list[str] = []
    handle_rows: list[dict[str, Any]] = []
    for key in required_handles:
        value = handles.get(key)
        if value is None:
            missing_handles.append(key)
            handle_rows.append(
                {
                    "handle": key,
                    "status": "missing",
                    "value": "",
                    "key": key,
                    "raw_value": None,
                    "state": "missing",
                    "projects_blocker": True,
                }
            )
            continue
        placeholder = is_placeholder(value)
        wildcard = is_wildcard(value)
        state = "resolved"
        if placeholder:
            state = "placeholder"
            placeholder_handles.append(key)
        elif wildcard:
            state = "wildcard"
            wildcard_handles.append(key)
        handle_rows.append(
            {
                "handle": key,
                "status": state,
                "value": value,
                "key": key,
                "raw_value": value,
                "state": state,
                "projects_blocker": state != "resolved",
            }
        )

    if missing_handles or placeholder_handles or wildcard_handles:
        blockers.append({"code": "M11-B1", "message": "Required M11.A handles are missing, placeholder, or wildcard-valued."})

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M11.B_READY" if overall_pass else "HOLD_REMEDIATE"
    verdict = "ADVANCE_TO_M11_B" if overall_pass else "HOLD_REMEDIATE"

    snapshot = {
        "captured_at_utc": captured_at,
        "phase": "M11.A",
        "phase_id": "P14",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "upstream_m10_execution": upstream_m10_execution,
        "upstream_m10j_execution": upstream_m10j_execution,
        "upstream_m10i_execution": upstream_m10i_execution,
        "upstream_m10_summary_key": m10_summary_key,
        "upstream_m10j_summary_key": m10j_summary_key,
        "upstream_m11_handoff_key": m11_handoff_key,
        "required_handle_count": len(required_handles),
        "resolved_handle_count": len(required_handles) - len(missing_handles) - len(placeholder_handles) - len(wildcard_handles),
        "missing_handles": missing_handles,
        "placeholder_handles": placeholder_handles,
        "wildcard_handles": wildcard_handles,
        "handle_matrix": handle_rows,
        "overall_pass": overall_pass,
    }

    register = {
        "captured_at_utc": captured_at,
        "phase": "M11.A",
        "phase_id": "P14",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "read_errors": read_errors,
        "upload_errors": upload_errors,
    }

    summary = {
        "captured_at_utc": captured_at,
        "phase": "M11.A",
        "phase_id": "P14",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "verdict": verdict,
        "next_gate": next_gate,
        "upstream_refs": {
            "m10_execution_id": upstream_m10_execution,
            "m10j_execution_id": upstream_m10j_execution,
            "m10i_execution_id": upstream_m10i_execution,
        },
        "artifact_keys": {
            "m11a_handle_closure_snapshot": f"evidence/dev_full/run_control/{execution_id}/m11a_handle_closure_snapshot.json",
            "m11a_blocker_register": f"evidence/dev_full/run_control/{execution_id}/m11a_blocker_register.json",
            "m11a_execution_summary": f"evidence/dev_full/run_control/{execution_id}/m11a_execution_summary.json",
        },
    }

    artifacts = {
        "m11a_handle_closure_snapshot.json": snapshot,
        "m11a_blocker_register.json": register,
        "m11a_execution_summary.json": summary,
    }
    write_local_artifacts(run_dir, artifacts)

    run_control_prefix = f"evidence/dev_full/run_control/{execution_id}"
    for name, payload in artifacts.items():
        key = f"{run_control_prefix}/{name}"
        try:
            s3_put_json(s3, evidence_bucket, key, payload)
        except (BotoCoreError, ClientError, ValueError) as exc:
            upload_errors.append({"artifact": name, "error": type(exc).__name__, "key": key})

    if upload_errors:
        blockers = list(blockers)
        blockers.append({"code": "M11-B12", "message": "Failed to publish/readback one or more M11.A artifacts."})
        blockers = dedupe_blockers(blockers)
        register["upload_errors"] = upload_errors
        register["blockers"] = blockers
        register["blocker_count"] = len(blockers)
        summary["overall_pass"] = False
        summary["verdict"] = "HOLD_REMEDIATE"
        summary["next_gate"] = "HOLD_REMEDIATE"
        summary["blocker_count"] = len(blockers)
        write_local_artifacts(run_dir, artifacts)

    out = {
        "execution_id": execution_id,
        "overall_pass": summary["overall_pass"],
        "blocker_count": summary["blocker_count"],
        "next_gate": summary["next_gate"],
        "run_dir": str(run_dir),
        "run_control_prefix": f"s3://{evidence_bucket}/{run_control_prefix}/",
    }
    print(json.dumps(out, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
