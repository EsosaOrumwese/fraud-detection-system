#!/usr/bin/env python3
"""Managed M8.C closure-input readiness artifact builder."""

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


def render_pattern(pattern: str, platform_run_id: str) -> str:
    return pattern.replace("{platform_run_id}", platform_run_id)


def s3_get_json(s3_client: Any, bucket: str, key: str) -> dict[str, Any]:
    body = s3_client.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    return json.loads(body)


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


def main() -> int:
    env = dict(os.environ)
    execution_id = env.get("M8C_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M8C_RUN_DIR", "").strip()
    bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m8b_execution = env.get("UPSTREAM_M8B_EXECUTION", "").strip()
    upstream_m7_execution = env.get("UPSTREAM_M7_EXECUTION", "").strip()
    upstream_m6_execution = env.get("UPSTREAM_M6_EXECUTION", "").strip()
    upstream_m7k_execution = env.get("UPSTREAM_M7K_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M8C_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M8C_RUN_DIR is required.")
    if not bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m8b_execution or not upstream_m7_execution or not upstream_m6_execution or not upstream_m7k_execution:
        raise SystemExit("UPSTREAM_M8B_EXECUTION, UPSTREAM_M7_EXECUTION, UPSTREAM_M6_EXECUTION, and UPSTREAM_M7K_EXECUTION are required.")

    run_dir = Path(run_dir_raw)
    captured = now_utc()
    s3 = boto3.client("s3", region_name=aws_region)
    handles = parse_handles(HANDLES_PATH)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []
    evidence_rows: list[dict[str, Any]] = []

    m8b_key = f"evidence/dev_full/run_control/{upstream_m8b_execution}/m8b_execution_summary.json"
    m7_handoff_key = f"evidence/dev_full/run_control/{upstream_m7_execution}/m8_handoff_pack.json"
    m6_summary_key = f"evidence/dev_full/run_control/{upstream_m6_execution}/m6_execution_summary.json"

    m8b_summary: dict[str, Any] | None = None
    m7_handoff: dict[str, Any] | None = None
    m6_summary: dict[str, Any] | None = None

    for key, target in [(m8b_key, "m8b"), (m7_handoff_key, "m7"), (m6_summary_key, "m6")]:
        try:
            data = s3_get_json(s3, bucket, key)
            if target == "m8b":
                m8b_summary = data
            elif target == "m7":
                m7_handoff = data
            else:
                m6_summary = data
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": key, "error": type(exc).__name__})
            blockers.append({"code": "M8-B3", "message": f"Required upstream evidence unreadable: {key}"})

    platform_run_id = env.get("PLATFORM_RUN_ID", "").strip()
    scenario_run_id = env.get("SCENARIO_RUN_ID", "").strip()

    if m8b_summary:
        if not (bool(m8b_summary.get("overall_pass")) and str(m8b_summary.get("next_gate", "")).strip() == "M8.C_READY"):
            blockers.append({"code": "M8-B3", "message": "Upstream M8.B gate is not M8.C_READY."})
        if not platform_run_id:
            platform_run_id = str(m8b_summary.get("platform_run_id", "")).strip()
        if not scenario_run_id:
            scenario_run_id = str(m8b_summary.get("scenario_run_id", "")).strip()

    if not platform_run_id or not scenario_run_id:
        blockers.append({"code": "M8-B3", "message": "Active run scope unresolved for M8.C."})

    p8e = p9e = p10e = ""
    if m7_handoff:
        if str(m7_handoff.get("m8_entry_gate", "")).strip() != "M8_READY":
            blockers.append({"code": "M8-B3", "message": "M7 handoff is not in M8_READY posture."})
        refs = m7_handoff.get("upstream_refs", {})
        p8e = str(refs.get("p8e_execution_id", "")).strip()
        p9e = str(refs.get("p9e_execution_id", "")).strip()
        p10e = str(refs.get("p10e_execution_id", "")).strip()
        if not p8e or not p9e or not p10e:
            blockers.append({"code": "M8-B3", "message": "M7 handoff missing P8/P9/P10 execution refs."})

    m6i = ""
    if m6_summary:
        if not bool(m6_summary.get("overall_pass")):
            blockers.append({"code": "M8-B3", "message": "M6 summary is not overall_pass=true."})
        m6i = str(m6_summary.get("upstream_refs", {}).get("m6i_execution_id", "")).strip()
        if not m6i:
            blockers.append({"code": "M8-B3", "message": "M6 summary missing P7 execution ref (m6i_execution_id)."})

    required_json_keys = [
        ("P7", f"evidence/dev_full/run_control/{m6i}/m6i_execution_summary.json"),
        ("P7", f"evidence/dev_full/run_control/{m6i}/m6i_p7_gate_rollup_matrix.json"),
        ("P7", f"evidence/dev_full/run_control/{m6i}/m6i_p7_gate_verdict.json"),
        ("P8", f"evidence/dev_full/run_control/{p8e}/p8e_execution_summary.json"),
        ("P8", f"evidence/dev_full/run_control/{p8e}/p8e_rtdl_gate_rollup_matrix.json"),
        ("P8", f"evidence/dev_full/run_control/{p8e}/p8e_rtdl_gate_verdict.json"),
        ("P9", f"evidence/dev_full/run_control/{p9e}/p9e_execution_summary.json"),
        ("P9", f"evidence/dev_full/run_control/{p9e}/p9e_decision_chain_rollup_matrix.json"),
        ("P9", f"evidence/dev_full/run_control/{p9e}/p9e_decision_chain_verdict.json"),
        ("P10", f"evidence/dev_full/run_control/{p10e}/p10e_execution_summary.json"),
        ("P10", f"evidence/dev_full/run_control/{p10e}/p10e_case_labels_rollup_matrix.json"),
        ("P10", f"evidence/dev_full/run_control/{p10e}/p10e_case_labels_verdict.json"),
        ("M7", f"evidence/dev_full/run_control/{upstream_m7_execution}/m7_execution_summary.json"),
        ("M7", f"evidence/dev_full/run_control/{upstream_m7_execution}/m7_rollup_matrix.json"),
        ("M7K", f"evidence/dev_full/run_control/{upstream_m7k_execution}/m7k_throughput_cert_execution_summary.json"),
        ("M7K", f"evidence/dev_full/run_control/{upstream_m7k_execution}/m7k_throughput_cert_verdict.json"),
        ("M7K", f"evidence/dev_full/run_control/{upstream_m7k_execution}/m7k_control_ingress_sentinel_snapshot.json"),
    ]

    for group, key in required_json_keys:
        if "//" in key or key.endswith("//") or "None" in key:
            blockers.append({"code": "M8-B3", "message": f"Derived invalid key for {group}: {key}"})
            evidence_rows.append({"group": group, "key": key, "readable": False, "reason": "invalid_derived_key"})
            continue
        try:
            obj = s3_get_json(s3, bucket, key)
            row = {"group": group, "key": key, "readable": True, "phase": obj.get("phase")}
            if key.endswith("_execution_summary.json"):
                if "overall_pass" not in obj or not bool(obj.get("overall_pass")):
                    blockers.append({"code": "M8-B3", "message": f"Summary not green: {key}"})
                    row["summary_green"] = False
                else:
                    row["summary_green"] = True
                if str(obj.get("platform_run_id", platform_run_id)).strip() != platform_run_id:
                    blockers.append({"code": "M8-B3", "message": f"Run-scope drift in summary: {key}"})
                    row["run_scope_ok"] = False
                else:
                    row["run_scope_ok"] = True
            evidence_rows.append(row)
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": key, "error": type(exc).__name__})
            blockers.append({"code": "M8-B3", "message": f"Required closure evidence unreadable: {key}"})
            evidence_rows.append({"group": group, "key": key, "readable": False})

    file_pattern_keys = [
        "RECEIPT_SUMMARY_PATH_PATTERN",
        "KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN",
        "QUARANTINE_SUMMARY_PATH_PATTERN",
    ]
    for handle_key in file_pattern_keys:
        pattern = handles.get(handle_key)
        if pattern is None or is_placeholder(pattern):
            blockers.append({"code": "M8-B3", "message": f"Handle missing/placeholder: {handle_key}"})
            continue
        key = render_pattern(str(pattern), platform_run_id)
        try:
            obj = s3_get_json(s3, bucket, key)
            row = {"group": "RUN_SCOPE_FILE", "handle": handle_key, "key": key, "readable": True}
            if str(obj.get("platform_run_id", platform_run_id)).strip() != platform_run_id:
                blockers.append({"code": "M8-B3", "message": f"Run-scope drift in run-scoped evidence: {key}"})
                row["run_scope_ok"] = False
            else:
                row["run_scope_ok"] = True
            evidence_rows.append(row)
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": key, "error": type(exc).__name__})
            blockers.append({"code": "M8-B3", "message": f"Run-scoped evidence unreadable: {key}"})
            evidence_rows.append({"group": "RUN_SCOPE_FILE", "handle": handle_key, "key": key, "readable": False})

    prefix_pattern_keys = [
        "RTDL_CORE_EVIDENCE_PATH_PATTERN",
        "DECISION_LANE_EVIDENCE_PATH_PATTERN",
        "CASE_LABELS_EVIDENCE_PATH_PATTERN",
    ]
    for handle_key in prefix_pattern_keys:
        pattern = handles.get(handle_key)
        if pattern is None or is_placeholder(pattern):
            blockers.append({"code": "M8-B3", "message": f"Handle missing/placeholder: {handle_key}"})
            continue
        prefix = render_pattern(str(pattern), platform_run_id)
        if not prefix.endswith("/"):
            prefix = f"{prefix}/"
        try:
            page = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1000)
            count = int(page.get("KeyCount", 0))
            contents = page.get("Contents", [])
            json_count = len([obj for obj in contents if str(obj.get("Key", "")).endswith(".json")])
            row = {"group": "RUN_SCOPE_PREFIX", "handle": handle_key, "prefix": prefix, "key_count": count, "json_count": json_count}
            if count == 0 or json_count == 0:
                blockers.append({"code": "M8-B3", "message": f"Run-scoped prefix missing JSON evidence: {prefix}"})
                row["readable"] = False
            else:
                row["readable"] = True
            evidence_rows.append(row)
        except (BotoCoreError, ClientError) as exc:
            read_errors.append({"surface": prefix, "error": type(exc).__name__})
            blockers.append({"code": "M8-B3", "message": f"Run-scoped prefix unreadable: {prefix}"})
            evidence_rows.append({"group": "RUN_SCOPE_PREFIX", "handle": handle_key, "prefix": prefix, "readable": False})

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M8.D_READY" if overall_pass else "HOLD_REMEDIATE"

    snapshot = {
        "captured_at_utc": captured,
        "phase": "M8.C",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "upstream_refs": {
            "m8b_execution": upstream_m8b_execution,
            "m7_execution": upstream_m7_execution,
            "m6_execution": upstream_m6_execution,
            "m7k_execution": upstream_m7k_execution,
            "p7_execution": m6i,
            "p8_execution": p8e,
            "p9_execution": p9e,
            "p10_execution": p10e,
        },
        "required_evidence_count": len(required_json_keys) + len(file_pattern_keys) + len(prefix_pattern_keys),
        "evidence_rows": evidence_rows,
        "overall_pass": overall_pass,
    }

    register = {
        "captured_at_utc": captured,
        "phase": "M8.C",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "read_errors": read_errors,
        "upload_errors": upload_errors,
    }

    summary = {
        "captured_at_utc": captured,
        "phase": "M8.C",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "next_gate": next_gate,
    }

    artifacts = {
        "m8c_closure_input_readiness_snapshot.json": snapshot,
        "m8c_blocker_register.json": register,
        "m8c_execution_summary.json": summary,
    }

    write_local_artifacts(run_dir, artifacts)

    prefix = f"evidence/dev_full/run_control/{execution_id}"
    for name, payload in artifacts.items():
        key = f"{prefix}/{name}"
        try:
            s3_put_json(s3, bucket, key, payload)
        except (BotoCoreError, ClientError, ValueError) as exc:
            upload_errors.append({"artifact": name, "error": type(exc).__name__, "key": key})

    if upload_errors:
        register["upload_errors"] = upload_errors
        register["blockers"].append({"code": "M8-B12", "message": "Failed to publish/readback one or more M8.C artifacts."})
        register["blocker_count"] = len(register["blockers"])
        summary["overall_pass"] = False
        summary["next_gate"] = "HOLD_REMEDIATE"
        summary["blocker_count"] = register["blocker_count"]
        write_local_artifacts(run_dir, artifacts)

    out = {
        "execution_id": execution_id,
        "overall_pass": summary["overall_pass"],
        "blocker_count": summary["blocker_count"],
        "run_dir": str(run_dir),
        "run_control_prefix": f"s3://{bucket}/{prefix}/",
    }
    print(json.dumps(out, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
