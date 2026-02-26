#!/usr/bin/env python3
"""Managed M8.I P11 rollup verdict + M9 handoff publisher."""

from __future__ import annotations

import json
import os
import re
import time
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


def is_placeholder(v: Any) -> bool:
    s = str(v or "").strip().lower()
    if not s:
        return True
    if s in {"tbd", "todo", "none", "null", "unset"}:
        return True
    if "placeholder" in s or "to_pin" in s:
        return True
    if "<" in s and ">" in s:
        return True
    return False


def dedupe(blockers: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for b in blockers:
        code = str(b.get("code", "")).strip()
        msg = str(b.get("message", "")).strip()
        sig = (code, msg)
        if sig in seen:
            continue
        seen.add(sig)
        out.append({"code": code, "message": msg})
    return out


def s3_get_json(s3: Any, bucket: str, key: str) -> dict[str, Any]:
    raw = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("json_not_object")
    return payload


def s3_put_json(s3: Any, bucket: str, key: str, payload: dict[str, Any]) -> None:
    body = (json.dumps(payload, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
    s3.head_object(Bucket=bucket, Key=key)


def write_local(run_dir: Path, artifacts: dict[str, dict[str, Any]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in artifacts.items():
        (run_dir / name).write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def render_pattern(pattern: str, platform_run_id: str) -> str:
    return pattern.replace("{platform_run_id}", platform_run_id)


def has_secret_like_payload(obj: Any) -> bool:
    risky_value_patterns = [
        "-----begin private key-----",
        "-----begin rsa private key-----",
        "akia",
        "aws_secret_access_key",
        "x-ig-api-key",
    ]
    risky_key_patterns = [
        "password",
        "api_key",
        "secret_key",
        "secret",
        "token",
    ]
    key_allow = {"non_secret_policy"}

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
            # protect against obvious bearer style secrets
            if len(txt) > 40 and ("token" in parent_key or "secret" in parent_key):
                return True
            return False
        return False

    return _walk(obj)


def main() -> int:
    start = time.time()
    env = dict(os.environ)

    execution_id = env.get("M8I_EXECUTION_ID", "").strip()
    run_dir = Path(env.get("M8I_RUN_DIR", "").strip())
    evidence_bucket = env.get("EVIDENCE_BUCKET", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M8I_EXECUTION_ID is required.")
    if not str(run_dir):
        raise SystemExit("M8I_RUN_DIR is required.")
    if not evidence_bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")

    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    upload_errors: list[dict[str, str]] = []

    required_handles = {
        "S3_EVIDENCE_BUCKET": str(handles.get("S3_EVIDENCE_BUCKET", "")).strip(),
        "S3_OBJECT_STORE_BUCKET": str(handles.get("S3_OBJECT_STORE_BUCKET", "")).strip(),
        "SPINE_RUN_REPORT_PATH_PATTERN": str(handles.get("SPINE_RUN_REPORT_PATH_PATTERN", "")).strip(),
        "SPINE_RECONCILIATION_PATH_PATTERN": str(handles.get("SPINE_RECONCILIATION_PATH_PATTERN", "")).strip(),
        "SPINE_NON_REGRESSION_PACK_PATTERN": str(handles.get("SPINE_NON_REGRESSION_PACK_PATTERN", "")).strip(),
        "GOV_APPEND_LOG_PATH_PATTERN": str(handles.get("GOV_APPEND_LOG_PATH_PATTERN", "")).strip(),
        "GOV_RUN_CLOSE_MARKER_PATH_PATTERN": str(handles.get("GOV_RUN_CLOSE_MARKER_PATH_PATTERN", "")).strip(),
    }
    unresolved = [k for k, v in required_handles.items() if is_placeholder(v)]
    if unresolved:
        blockers.append({"code": "M8-B9", "message": f"Required handles unresolved: {','.join(sorted(unresolved))}."})
    if required_handles["S3_EVIDENCE_BUCKET"] and required_handles["S3_EVIDENCE_BUCKET"] != evidence_bucket:
        blockers.append({"code": "M8-B9", "message": "EVIDENCE_BUCKET does not match handle registry S3_EVIDENCE_BUCKET."})

    phase_inputs = [
        ("M8.A", env.get("UPSTREAM_M8A_EXECUTION", "m8a_p11_handle_closure_20260226T050813Z").strip(), "m8a_execution_summary.json", "M8.B_READY"),
        ("M8.B", env.get("UPSTREAM_M8B_EXECUTION", "m8b_p11_runtime_lock_readiness_20260226T052700Z").strip(), "m8b_execution_summary.json", "M8.C_READY"),
        ("M8.C", env.get("UPSTREAM_M8C_EXECUTION", "m8c_p11_closure_input_readiness_20260226T053157Z").strip(), "m8c_execution_summary.json", "M8.D_READY"),
        ("M8.D", env.get("UPSTREAM_M8D_EXECUTION", "m8d_p11_single_writer_probe_20260226T062710Z").strip(), "m8d_execution_summary.json", "M8.E_READY"),
        ("M8.E", env.get("UPSTREAM_M8E_EXECUTION", "m8e_p11_reporter_one_shot_20260226T062735Z").strip(), "m8e_execution_summary.json", "M8.F_READY"),
        ("M8.F", env.get("UPSTREAM_M8F_EXECUTION", "m8f_p11_closure_bundle_20260226T062814Z").strip(), "m8f_execution_summary.json", "M8.G_READY"),
        ("M8.G", env.get("UPSTREAM_M8G_EXECUTION", "m8g_p11_non_regression_20260226T062919Z").strip(), "m8g_execution_summary.json", "M8.H_READY"),
        ("M8.H", env.get("UPSTREAM_M8H_EXECUTION", "m8h_p11_governance_close_marker_20260226T063647Z").strip(), "m8h_execution_summary.json", "M8.I_READY"),
    ]

    source_phase_matrix: list[dict[str, Any]] = []
    summary_payloads: dict[str, dict[str, Any]] = {}
    platform_run_id = ""
    scenario_run_id = ""

    for phase_name, phase_exec, summary_file, expected_next_gate in phase_inputs:
        key = f"evidence/dev_full/run_control/{phase_exec}/{summary_file}"
        row = {
            "phase": phase_name,
            "execution_id": phase_exec,
            "summary_key": key,
            "expected_next_gate": expected_next_gate,
            "readable": False,
            "overall_pass": False,
            "actual_next_gate": "",
            "next_gate_ok": False,
            "run_scope_ok": False,
        }
        try:
            payload = s3_get_json(s3, evidence_bucket, key)
            summary_payloads[phase_name] = payload
            row["readable"] = True
            row["overall_pass"] = bool(payload.get("overall_pass"))
            row["actual_next_gate"] = str(payload.get("next_gate", "")).strip()
            row["next_gate_ok"] = row["actual_next_gate"] == expected_next_gate
            if not row["overall_pass"]:
                blockers.append({"code": "M8-B9", "message": f"{phase_name} summary is not pass."})
            if not row["next_gate_ok"]:
                blockers.append({"code": "M8-B9", "message": f"{phase_name} next_gate mismatch."})

            row_platform = str(payload.get("platform_run_id", "")).strip()
            row_scenario = str(payload.get("scenario_run_id", "")).strip()
            if not platform_run_id:
                platform_run_id = row_platform
            if not scenario_run_id:
                scenario_run_id = row_scenario
            row["run_scope_ok"] = bool(row_platform and row_scenario and row_platform == platform_run_id and row_scenario == scenario_run_id)
            if not row["run_scope_ok"]:
                blockers.append({"code": "M8-B9", "message": f"{phase_name} run-scope mismatch."})
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": key, "error": type(exc).__name__})
            blockers.append({"code": "M8-B9", "message": f"{phase_name} summary unreadable."})
        source_phase_matrix.append(row)

    if not platform_run_id or not scenario_run_id:
        blockers.append({"code": "M8-B9", "message": "Canonical run scope unresolved from M8 source summaries."})

    entry_surface_checks: list[dict[str, Any]] = []
    required_evidence_refs: dict[str, str] = {}
    object_store_bucket = required_handles["S3_OBJECT_STORE_BUCKET"]
    if platform_run_id:
        required_evidence_refs = {
            "run_report_ref": render_pattern(required_handles["SPINE_RUN_REPORT_PATH_PATTERN"], platform_run_id),
            "reconciliation_ref": render_pattern(required_handles["SPINE_RECONCILIATION_PATH_PATTERN"], platform_run_id),
            "non_regression_pack_ref": render_pattern(required_handles["SPINE_NON_REGRESSION_PACK_PATTERN"], platform_run_id),
            "governance_append_log_ref": render_pattern(required_handles["GOV_APPEND_LOG_PATH_PATTERN"], platform_run_id),
            "governance_closure_marker_ref": render_pattern(required_handles["GOV_RUN_CLOSE_MARKER_PATH_PATTERN"], platform_run_id),
        }
        for ref_name, ref_key in required_evidence_refs.items():
            row = {"ref_name": ref_name, "key": ref_key, "readable": False, "projected_from_object_store": False}
            try:
                s3.head_object(Bucket=evidence_bucket, Key=ref_key)
                row["readable"] = True
            except (BotoCoreError, ClientError) as exc:
                # Deterministic projection for source-truth refs expected in evidence path.
                projected = False
                if ref_name in {"run_report_ref", "reconciliation_ref"} and object_store_bucket:
                    source_key = f"{platform_run_id}/obs/run_report.json" if ref_name == "run_report_ref" else f"{platform_run_id}/obs/reconciliation.json"
                    try:
                        src_obj = s3_get_json(s3, object_store_bucket, source_key)
                        s3_put_json(s3, evidence_bucket, ref_key, src_obj)
                        row["readable"] = True
                        row["projected_from_object_store"] = True
                        projected = True
                    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as proj_exc:
                        read_errors.append(
                            {
                                "surface": f"s3://{object_store_bucket}/{source_key}",
                                "error": type(proj_exc).__name__,
                                "projection_target": f"s3://{evidence_bucket}/{ref_key}",
                            }
                        )
                if not projected:
                    read_errors.append({"surface": f"s3://{evidence_bucket}/{ref_key}", "error": type(exc).__name__})
                    blockers.append({"code": "M8-B9", "message": f"M9 entry required reference unreadable: {ref_name}."})
            entry_surface_checks.append(row)

    blockers = dedupe(blockers)
    verdict = "ADVANCE_TO_M9" if len(blockers) == 0 else "HOLD_M8"
    next_gate = "M9_READY" if verdict == "ADVANCE_TO_M9" else "HOLD_REMEDIATE"
    overall_pass = verdict == "ADVANCE_TO_M9"
    elapsed = round(time.time() - start, 3)

    rollup = {
        "captured_at_utc": now_utc(),
        "phase": "M8.I",
        "phase_id": "P11",
        "m8_execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "source_phase_matrix": source_phase_matrix,
        "source_refs": {row["phase"]: row["summary_key"] for row in source_phase_matrix},
        "entry_surface_checks": entry_surface_checks,
        "blockers": blockers,
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "elapsed_seconds": elapsed,
    }

    verdict_payload = {
        "captured_at_utc": now_utc(),
        "phase": "M8.I",
        "phase_id": "P11",
        "m8_execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "verdict": verdict,
        "next_gate": next_gate,
        "source_rollup_ref": f"evidence/dev_full/run_control/{execution_id}/m8i_p11_rollup_matrix.json",
        "blockers": blockers,
        "overall_pass": overall_pass,
    }

    handoff_id = f"m9_handoff_{execution_id}"
    handoff_payload = {
        "handoff_id": handoff_id,
        "generated_at_utc": now_utc(),
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "m8_verdict": verdict,
        "m8_overall_pass": overall_pass,
        "m8_execution_id": execution_id,
        "source_verdict_ref": f"evidence/dev_full/run_control/{execution_id}/m8i_p11_verdict.json",
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
        "m9_entry_gate": {
            "required_verdict": "ADVANCE_TO_M9",
            "required_overall_pass": True,
            "next_gate": "M9_READY",
        },
        "non_secret_policy": {
            "enforced": True,
            "blocked_patterns": ["password", "secret", "token", "AKIA", "PRIVATE_KEY"],
        },
    }

    if has_secret_like_payload(handoff_payload):
        blockers.append({"code": "M8-B10", "message": "handoff payload violates non-secret policy."})
        blockers = dedupe(blockers)
        verdict = "HOLD_M8"
        next_gate = "HOLD_REMEDIATE"
        overall_pass = False
        verdict_payload["verdict"] = verdict
        verdict_payload["next_gate"] = next_gate
        verdict_payload["overall_pass"] = False
        verdict_payload["blockers"] = blockers
        rollup["overall_pass"] = False
        rollup["next_gate"] = next_gate
        rollup["blockers"] = blockers
        handoff_payload["m8_verdict"] = verdict
        handoff_payload["m8_overall_pass"] = False

    register = {
        "captured_at_utc": now_utc(),
        "phase": "M8.I",
        "phase_id": "P11",
        "m8_execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "read_errors": read_errors,
        "upload_errors": upload_errors,
    }

    summary = {
        "captured_at_utc": now_utc(),
        "phase": "M8.I",
        "phase_id": "P11",
        "m8_execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "verdict": verdict,
        "next_gate": next_gate,
        "elapsed_seconds": elapsed,
        "durable_artifacts": {
            "m8i_rollup_key": f"evidence/dev_full/run_control/{execution_id}/m8i_p11_rollup_matrix.json",
            "m8i_verdict_key": f"evidence/dev_full/run_control/{execution_id}/m8i_p11_verdict.json",
            "m9_handoff_key": f"evidence/dev_full/run_control/{execution_id}/m9_handoff_pack.json",
            "m8i_blocker_register_key": f"evidence/dev_full/run_control/{execution_id}/m8i_blocker_register.json",
            "m8i_execution_summary_key": f"evidence/dev_full/run_control/{execution_id}/m8i_execution_summary.json",
        },
    }

    artifacts = {
        "m8i_p11_rollup_matrix.json": rollup,
        "m8i_p11_verdict.json": verdict_payload,
        "m9_handoff_pack.json": handoff_payload,
        "m8i_blocker_register.json": register,
        "m8i_execution_summary.json": summary,
    }
    write_local(run_dir, artifacts)

    run_control_prefix = f"evidence/dev_full/run_control/{execution_id}"
    for name, payload in artifacts.items():
        key = f"{run_control_prefix}/{name}"
        try:
            s3_put_json(s3, evidence_bucket, key, payload)
        except (BotoCoreError, ClientError, ValueError) as exc:
            upload_errors.append({"artifact": name, "key": key, "error": type(exc).__name__})

    if upload_errors:
        blockers.append({"code": "M8-B12", "message": "Failed to publish/readback one or more M8.I artifacts."})
        blockers = dedupe(blockers)
        verdict = "HOLD_M8"
        next_gate = "HOLD_REMEDIATE"
        overall_pass = False
        elapsed = round(time.time() - start, 3)
        rollup["blockers"] = blockers
        rollup["overall_pass"] = overall_pass
        rollup["next_gate"] = next_gate
        rollup["elapsed_seconds"] = elapsed
        verdict_payload["blockers"] = blockers
        verdict_payload["overall_pass"] = overall_pass
        verdict_payload["verdict"] = verdict
        verdict_payload["next_gate"] = next_gate
        handoff_payload["m8_verdict"] = verdict
        handoff_payload["m8_overall_pass"] = overall_pass
        register["blockers"] = blockers
        register["blocker_count"] = len(blockers)
        register["upload_errors"] = upload_errors
        summary["overall_pass"] = overall_pass
        summary["blocker_count"] = len(blockers)
        summary["verdict"] = verdict
        summary["next_gate"] = next_gate
        summary["elapsed_seconds"] = elapsed
        artifacts = {
            "m8i_p11_rollup_matrix.json": rollup,
            "m8i_p11_verdict.json": verdict_payload,
            "m9_handoff_pack.json": handoff_payload,
            "m8i_blocker_register.json": register,
            "m8i_execution_summary.json": summary,
        }
        write_local(run_dir, artifacts)

    print(
        json.dumps(
            {
                "execution_id": execution_id,
                "overall_pass": summary["overall_pass"],
                "verdict": summary["verdict"],
                "blocker_count": summary["blocker_count"],
                "next_gate": summary["next_gate"],
                "run_dir": str(run_dir),
                "run_control_prefix": f"s3://{evidence_bucket}/{run_control_prefix}/",
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
