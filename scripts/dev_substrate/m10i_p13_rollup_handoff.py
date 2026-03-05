#!/usr/bin/env python3
"""Managed M10.I P13 rollup verdict + M11 handoff publisher."""

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
    if s in {"*", "**"}:
        return True
    if "SSM_*" in s or "RDS_*" in s or "SVC_*" in s:
        return True
    return False


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


def has_secret_like_payload(obj: Any) -> bool:
    risky_value_patterns = [
        "-----begin private key-----",
        "-----begin rsa private key-----",
        "akia",
        "aws_secret_access_key",
        "x-ig-api-key",
    ]
    risky_key_patterns = ["password", "api_key", "secret", "token"]
    key_allow = {"non_secret_policy", "blocked_patterns"}

    def _walk(v: Any, parent_key: str = "") -> bool:
        if isinstance(v, dict):
            for k, vv in v.items():
                k_norm = str(k).strip().lower()
                if k_norm not in key_allow and any(p in k_norm for p in risky_key_patterns):
                    return True
                if _walk(vv, parent_key=k_norm):
                    return True
            return False
        if isinstance(v, list):
            for item in v:
                if _walk(item, parent_key=parent_key):
                    return True
            return False
        if isinstance(v, str):
            if parent_key in {"blocked_patterns"}:
                return False
            txt = v.strip().lower()
            if any(p in txt for p in risky_value_patterns):
                return True
            if len(txt) > 40 and ("token" in parent_key or "secret" in parent_key):
                return True
            return False
        return False

    return _walk(obj)


def main() -> int:
    env = dict(os.environ)
    execution_id = env.get("M10I_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M10I_RUN_DIR", "").strip()
    bucket = env.get("EVIDENCE_BUCKET", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M10I_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M10I_RUN_DIR is required.")
    if not bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")

    upstream_matrix = [
        ("M10.A", env.get("UPSTREAM_M10A_EXECUTION", "").strip(), "m10a_execution_summary.json", "M10.B_READY"),
        ("M10.B", env.get("UPSTREAM_M10B_EXECUTION", "").strip(), "m10b_execution_summary.json", "M10.C_READY"),
        ("M10.C", env.get("UPSTREAM_M10C_EXECUTION", "").strip(), "m10c_execution_summary.json", "M10.D_READY"),
        ("M10.D", env.get("UPSTREAM_M10D_EXECUTION", "").strip(), "m10d_execution_summary.json", "M10.E_READY"),
        ("M10.E", env.get("UPSTREAM_M10E_EXECUTION", "").strip(), "m10e_execution_summary.json", "M10.F_READY"),
        ("M10.F", env.get("UPSTREAM_M10F_EXECUTION", "").strip(), "m10f_execution_summary.json", "M10.G_READY"),
        ("M10.G", env.get("UPSTREAM_M10G_EXECUTION", "").strip(), "m10g_execution_summary.json", "M10.H_READY"),
        ("M10.H", env.get("UPSTREAM_M10H_EXECUTION", "").strip(), "m10h_execution_summary.json", "M10.I_READY"),
    ]
    for phase_name, phase_exec, _, _ in upstream_matrix:
        if not phase_exec:
            raise SystemExit(f"UPSTREAM_{phase_name.replace('.', '').upper()}_EXECUTION is required.")

    run_dir = Path(run_dir_raw)
    captured = now_utc()
    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    required_handles = ["S3_EVIDENCE_BUCKET", "S3_RUN_CONTROL_ROOT_PATTERN"]
    missing_handles: list[str] = []
    placeholder_handles: list[str] = []
    wildcard_handles: list[str] = []
    resolved_handle_values: dict[str, Any] = {}
    for key in required_handles:
        value = handles.get(key)
        if value is None:
            missing_handles.append(key)
            continue
        resolved_handle_values[key] = value
        if is_placeholder(value):
            placeholder_handles.append(key)
        if is_wildcard(value):
            wildcard_handles.append(key)
    if missing_handles or placeholder_handles or wildcard_handles:
        blockers.append({"code": "M10-B9", "message": "Required M10.I handles are missing, placeholder, or wildcard-valued."})

    bucket_from_handle = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    if bucket_from_handle and bucket_from_handle != bucket:
        blockers.append({"code": "M10-B9", "message": "EVIDENCE_BUCKET does not match S3_EVIDENCE_BUCKET handle."})

    source_phase_matrix: list[dict[str, Any]] = []
    summary_payloads: dict[str, dict[str, Any]] = {}
    platform_values: list[str] = []
    scenario_values: list[str] = []

    for phase_name, phase_exec, summary_file, expected_next_gate in upstream_matrix:
        summary_key = f"evidence/dev_full/run_control/{phase_exec}/{summary_file}"
        row: dict[str, Any] = {
            "phase": phase_name,
            "execution_id": phase_exec,
            "summary_key": summary_key,
            "expected_next_gate": expected_next_gate,
            "readable": False,
            "overall_pass": False,
            "actual_next_gate": "",
            "next_gate_ok": False,
            "run_scope_ok": False,
        }
        try:
            payload = s3_get_json(s3, bucket, summary_key)
            summary_payloads[phase_name] = payload
            row["readable"] = True
            row["overall_pass"] = bool(payload.get("overall_pass"))
            row["actual_next_gate"] = str(payload.get("next_gate", "")).strip()
            row["next_gate_ok"] = row["actual_next_gate"] == expected_next_gate

            p = str(payload.get("platform_run_id", "")).strip()
            s = str(payload.get("scenario_run_id", "")).strip()
            if p:
                platform_values.append(p)
            if s:
                scenario_values.append(s)

            if not row["overall_pass"]:
                blockers.append({"code": "M10-B9", "message": f"{phase_name} summary is not pass."})
            if not row["next_gate_ok"]:
                blockers.append({"code": "M10-B9", "message": f"{phase_name} next_gate mismatch."})
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": summary_key, "error": type(exc).__name__})
            blockers.append({"code": "M10-B9", "message": f"{phase_name} summary unreadable."})
        source_phase_matrix.append(row)

    platform_unique = sorted(set([x for x in platform_values if x]))
    scenario_unique = sorted(set([x for x in scenario_values if x]))
    platform_run_id = platform_unique[0] if len(platform_unique) == 1 else ""
    scenario_run_id = scenario_unique[0] if len(scenario_unique) == 1 else ""

    for row in source_phase_matrix:
        payload = summary_payloads.get(row["phase"], {})
        p = str(payload.get("platform_run_id", "")).strip()
        s = str(payload.get("scenario_run_id", "")).strip()
        row["run_scope_ok"] = bool(platform_run_id and scenario_run_id and p == platform_run_id and s == scenario_run_id)
        if row["readable"] and not row["run_scope_ok"]:
            blockers.append({"code": "M10-B9", "message": f"{row['phase']} run-scope mismatch."})

    if len(platform_unique) != 1:
        blockers.append({"code": "M10-B9", "message": "platform_run_id is inconsistent across M10.A..M10.H summaries."})
    if len(scenario_unique) != 1:
        blockers.append({"code": "M10-B9", "message": "scenario_run_id is inconsistent across M10.A..M10.H summaries."})

    required_evidence_refs = {
        "m10a_handle_closure_ref": f"evidence/dev_full/run_control/{upstream_matrix[0][1]}/m10a_handle_closure_snapshot.json",
        "m10b_databricks_readiness_ref": f"evidence/dev_full/run_control/{upstream_matrix[1][1]}/m10b_databricks_readiness_snapshot.json",
        "m10c_input_binding_ref": f"evidence/dev_full/run_control/{upstream_matrix[2][1]}/m10c_input_binding_snapshot.json",
        "m10d_ofs_build_execution_ref": f"evidence/dev_full/run_control/{upstream_matrix[3][1]}/m10d_ofs_build_execution_snapshot.json",
        "m10e_quality_gate_ref": f"evidence/dev_full/run_control/{upstream_matrix[4][1]}/m10e_quality_gate_snapshot.json",
        "m10f_iceberg_commit_ref": f"evidence/dev_full/run_control/{upstream_matrix[5][1]}/m10f_iceberg_commit_snapshot.json",
        "m10g_manifest_fingerprint_ref": f"evidence/dev_full/run_control/{upstream_matrix[6][1]}/m10g_manifest_fingerprint_snapshot.json",
        "m10h_rollback_recipe_ref": f"evidence/dev_full/run_control/{upstream_matrix[7][1]}/m10h_rollback_recipe_snapshot.json",
    }
    for ref_name, ref_key in required_evidence_refs.items():
        if not ref_key:
            blockers.append({"code": "M10-B10", "message": f"Required handoff reference is unresolved: {ref_name}."})
            continue
        try:
            s3.head_object(Bucket=bucket, Key=ref_key)
        except (BotoCoreError, ClientError) as exc:
            read_errors.append({"surface": ref_key, "error": type(exc).__name__})
            blockers.append({"code": "M10-B10", "message": f"Required handoff reference unreadable: {ref_name}."})

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    verdict = "ADVANCE_TO_P14" if overall_pass else "HOLD_P13"
    next_gate = "M11_READY" if overall_pass else "HOLD_REMEDIATE"

    rollup_matrix = {
        "captured_at_utc": captured,
        "phase": "M10.I",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "source_phase_matrix": source_phase_matrix,
        "source_refs": {row["phase"]: row["summary_key"] for row in source_phase_matrix},
        "required_evidence_refs": required_evidence_refs,
        "resolved_handle_values": resolved_handle_values,
        "blockers": blockers,
        "overall_pass": overall_pass,
        "verdict": verdict,
        "next_gate": next_gate,
    }

    verdict_payload = {
        "captured_at_utc": captured,
        "phase": "M10.I",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "verdict": verdict,
        "next_gate": next_gate,
        "source_rollup_ref": f"evidence/dev_full/run_control/{execution_id}/m10i_p13_rollup_matrix.json",
        "blockers": blockers,
        "overall_pass": overall_pass,
    }

    handoff_payload = {
        "handoff_id": f"m11_handoff_{execution_id}",
        "generated_at_utc": captured,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "p13_verdict": verdict,
        "p13_overall_pass": overall_pass,
        "m10i_execution_id": execution_id,
        "source_verdict_ref": f"evidence/dev_full/run_control/{execution_id}/m10i_p13_gate_verdict.json",
        "phase_pass_matrix": [
            {
                "phase": row["phase"],
                "execution_id": row["execution_id"],
                "overall_pass": row["overall_pass"],
                "next_gate": row["actual_next_gate"],
            }
            for row in source_phase_matrix
        ],
        "required_evidence_refs": required_evidence_refs,
        "m11_entry_gate": {
            "required_verdict": "ADVANCE_TO_P14",
            "required_overall_pass": True,
            "next_gate": "M11_READY",
        },
        "non_secret_policy": {
            "enforced": True,
            "blocked_patterns": ["password", "secret", "token", "AKIA", "PRIVATE_KEY"],
        },
    }

    if has_secret_like_payload(handoff_payload):
        blockers.append({"code": "M10-B10", "message": "handoff payload violates non-secret policy."})
        blockers = dedupe_blockers(blockers)
        overall_pass = False
        verdict = "HOLD_P13"
        next_gate = "HOLD_REMEDIATE"
        rollup_matrix["blockers"] = blockers
        rollup_matrix["overall_pass"] = False
        rollup_matrix["verdict"] = verdict
        rollup_matrix["next_gate"] = next_gate
        verdict_payload["blockers"] = blockers
        verdict_payload["overall_pass"] = False
        verdict_payload["verdict"] = verdict
        verdict_payload["next_gate"] = next_gate
        handoff_payload["p13_overall_pass"] = False
        handoff_payload["p13_verdict"] = verdict
        handoff_payload["m11_entry_gate"]["next_gate"] = next_gate

    summary = {
        "captured_at_utc": captured,
        "phase": "M10.I",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "verdict": verdict,
        "next_gate": next_gate,
    }
    register = {
        "captured_at_utc": captured,
        "phase": "M10.I",
        "phase_id": "P13",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "blockers": blockers,
        "blocker_count": len(blockers),
        "read_errors": read_errors,
        "upload_errors": upload_errors,
    }

    artifacts = {
        "m10i_p13_rollup_matrix.json": rollup_matrix,
        "m10i_p13_gate_verdict.json": verdict_payload,
        "m11_handoff_pack.json": handoff_payload,
        "m10i_blocker_register.json": register,
        "m10i_execution_summary.json": summary,
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
        upload_blockers = blockers + [{"code": "M10-B12", "message": "Failed to publish/readback one or more M10.I artifacts."}]
        upload_blockers = dedupe_blockers(upload_blockers)
        summary["overall_pass"] = False
        summary["blocker_count"] = len(upload_blockers)
        summary["verdict"] = "HOLD_P13"
        summary["next_gate"] = "HOLD_REMEDIATE"
        rollup_matrix["blockers"] = upload_blockers
        rollup_matrix["overall_pass"] = False
        rollup_matrix["verdict"] = "HOLD_P13"
        rollup_matrix["next_gate"] = "HOLD_REMEDIATE"
        verdict_payload["blockers"] = upload_blockers
        verdict_payload["overall_pass"] = False
        verdict_payload["verdict"] = "HOLD_P13"
        verdict_payload["next_gate"] = "HOLD_REMEDIATE"
        register["upload_errors"] = upload_errors
        register["blockers"] = upload_blockers
        register["blocker_count"] = len(upload_blockers)
        artifacts["m10i_execution_summary.json"] = summary
        artifacts["m10i_p13_rollup_matrix.json"] = rollup_matrix
        artifacts["m10i_p13_gate_verdict.json"] = verdict_payload
        artifacts["m10i_blocker_register.json"] = register
        write_local_artifacts(run_dir, artifacts)

    out = {
        "execution_id": execution_id,
        "overall_pass": summary["overall_pass"],
        "blocker_count": summary["blocker_count"],
        "verdict": summary["verdict"],
        "next_gate": summary["next_gate"],
        "run_dir": str(run_dir),
        "run_control_prefix": f"s3://{bucket}/{prefix}/",
    }
    print(json.dumps(out, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
