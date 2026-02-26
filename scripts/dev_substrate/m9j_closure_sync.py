#!/usr/bin/env python3
"""Build and publish M9.J closure sync summary artifacts."""

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


def parse_utc(text: str | None) -> datetime | None:
    if not text:
        return None
    normalized = str(text).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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
    execution_id = env.get("M9J_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M9J_RUN_DIR", "").strip()
    evidence_bucket = env.get("EVIDENCE_BUCKET", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"

    if not execution_id:
        raise SystemExit("M9J_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M9J_RUN_DIR is required.")
    if not evidence_bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")

    upstream_execs = {
        "m9a": env.get("UPSTREAM_M9A_EXECUTION", "").strip(),
        "m9b": env.get("UPSTREAM_M9B_EXECUTION", "").strip(),
        "m9c": env.get("UPSTREAM_M9C_EXECUTION", "").strip(),
        "m9d": env.get("UPSTREAM_M9D_EXECUTION", "").strip(),
        "m9e": env.get("UPSTREAM_M9E_EXECUTION", "").strip(),
        "m9f": env.get("UPSTREAM_M9F_EXECUTION", "").strip(),
        "m9g": env.get("UPSTREAM_M9G_EXECUTION", "").strip(),
        "m9h": env.get("UPSTREAM_M9H_EXECUTION", "").strip(),
        "m9i": env.get("UPSTREAM_M9I_EXECUTION", "").strip(),
    }
    missing_upstreams = [k for k, v in upstream_execs.items() if not v]
    if missing_upstreams:
        raise SystemExit(f"Missing upstream execution ids: {','.join(missing_upstreams)}")

    run_dir = Path(run_dir_raw)
    captured_at = now_utc()
    handles = parse_handles(HANDLES_PATH)
    s3 = boto3.client("s3", region_name=aws_region)

    blockers: list[dict[str, str]] = []
    read_errors: list[str] = []
    upload_errors: list[str] = []

    required_handles = {
        "S3_EVIDENCE_BUCKET": handles.get("S3_EVIDENCE_BUCKET"),
        "S3_RUN_CONTROL_ROOT_PATTERN": handles.get("S3_RUN_CONTROL_ROOT_PATTERN"),
    }
    unresolved_handles = [k for k, v in required_handles.items() if is_placeholder(v)]
    if unresolved_handles:
        blockers.append({"code": "M9-B10", "message": f"Required closure handles unresolved: {','.join(sorted(unresolved_handles))}."})

    handle_evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    if handle_evidence_bucket and handle_evidence_bucket != evidence_bucket:
        blockers.append({"code": "M9-B10", "message": "EVIDENCE_BUCKET does not match S3_EVIDENCE_BUCKET handle."})

    summary_specs = [
        ("M9.A", upstream_execs["m9a"], "m9a_execution_summary.json", "M9.B_READY"),
        ("M9.B", upstream_execs["m9b"], "m9b_execution_summary.json", "M9.C_READY"),
        ("M9.C", upstream_execs["m9c"], "m9c_execution_summary.json", "M9.D_READY"),
        ("M9.D", upstream_execs["m9d"], "m9d_execution_summary.json", "M9.E_READY"),
        ("M9.E", upstream_execs["m9e"], "m9e_execution_summary.json", "M9.F_READY"),
        ("M9.F", upstream_execs["m9f"], "m9f_execution_summary.json", "M9.G_READY"),
        ("M9.G", upstream_execs["m9g"], "m9g_execution_summary.json", "M9.H_READY"),
        ("M9.H", upstream_execs["m9h"], "m9h_execution_summary.json", "M10_READY"),
        ("M9.I", upstream_execs["m9i"], "m9i_execution_summary.json", "M9.J_READY"),
    ]

    summary_matrix: list[dict[str, Any]] = []
    summary_payloads: dict[str, dict[str, Any]] = {}
    platform_values: list[str] = []
    scenario_values: list[str] = []
    upstream_times: list[datetime] = []
    for phase_name, phase_exec, summary_file, expected_next_gate in summary_specs:
        key = f"evidence/dev_full/run_control/{phase_exec}/{summary_file}"
        row: dict[str, Any] = {
            "phase": phase_name,
            "execution_id": phase_exec,
            "s3_key": key,
            "readable": False,
            "error": None,
            "overall_pass": False,
            "actual_next_gate": "",
            "expected_next_gate": expected_next_gate,
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
            p = str(payload.get("platform_run_id", "")).strip()
            s = str(payload.get("scenario_run_id", "")).strip()
            if p:
                platform_values.append(p)
            if s:
                scenario_values.append(s)
            t = parse_utc(str(payload.get("captured_at_utc", "")).strip())
            if t is not None:
                upstream_times.append(t)
            if not row["overall_pass"]:
                blockers.append({"code": "M9-B10", "message": f"{phase_name} summary is not pass."})
            if not row["next_gate_ok"]:
                blockers.append({"code": "M9-B10", "message": f"{phase_name} next_gate mismatch."})
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            row["error"] = type(exc).__name__
            read_errors.append(f"{phase_name}:{type(exc).__name__}:{key}")
            blockers.append({"code": "M9-B10", "message": f"{phase_name} summary unreadable."})
        summary_matrix.append(row)

    m9h_verdict = str(summary_payloads.get("M9.H", {}).get("verdict", "")).strip()
    if m9h_verdict != "ADVANCE_TO_P13":
        blockers.append({"code": "M9-B10", "message": "M9.H verdict is not ADVANCE_TO_P13."})
    m9i_verdict = str(summary_payloads.get("M9.I", {}).get("verdict", "")).strip()
    if m9i_verdict != "ADVANCE_TO_M9J":
        blockers.append({"code": "M9-B10", "message": "M9.I verdict is not ADVANCE_TO_M9J."})

    platform_unique = sorted(set([x for x in platform_values if x]))
    scenario_unique = sorted(set([x for x in scenario_values if x]))
    platform_run_id = platform_unique[0] if len(platform_unique) == 1 else ""
    scenario_run_id = scenario_unique[0] if len(scenario_unique) == 1 else ""

    if len(platform_unique) != 1:
        blockers.append({"code": "M9-B10", "message": "platform_run_id is inconsistent across M9 summaries."})
    if len(scenario_unique) != 1:
        blockers.append({"code": "M9-B10", "message": "scenario_run_id is inconsistent across M9 summaries."})

    for row in summary_matrix:
        payload = summary_payloads.get(str(row["phase"]), {})
        p = str(payload.get("platform_run_id", "")).strip()
        s = str(payload.get("scenario_run_id", "")).strip()
        row["run_scope_ok"] = bool(platform_run_id and scenario_run_id and p == platform_run_id and s == scenario_run_id)
        if row["readable"] and not row["run_scope_ok"]:
            blockers.append({"code": "M9-B10", "message": f"{row['phase']} run-scope mismatch."})

    contract_artifacts = {
        "m9a_handle_closure_snapshot": f"evidence/dev_full/run_control/{upstream_execs['m9a']}/m9a_handle_closure_snapshot.json",
        "m9b_handoff_scope_snapshot": f"evidence/dev_full/run_control/{upstream_execs['m9b']}/m9b_handoff_scope_snapshot.json",
        "m9c_replay_basis_receipt": f"evidence/dev_full/run_control/{upstream_execs['m9c']}/m9c_replay_basis_receipt.json",
        "m9d_asof_maturity_policy_snapshot": f"evidence/dev_full/run_control/{upstream_execs['m9d']}/m9d_asof_maturity_policy_snapshot.json",
        "m9e_leakage_guardrail_report": f"evidence/dev_full/run_control/{upstream_execs['m9e']}/m9e_leakage_guardrail_report.json",
        "m9f_surface_separation_snapshot": f"evidence/dev_full/run_control/{upstream_execs['m9f']}/m9f_surface_separation_snapshot.json",
        "m9g_learning_input_readiness_snapshot": f"evidence/dev_full/run_control/{upstream_execs['m9g']}/m9g_learning_input_readiness_snapshot.json",
        "m9h_p12_gate_verdict": f"evidence/dev_full/run_control/{upstream_execs['m9h']}/m9h_p12_gate_verdict.json",
        "m10_handoff_pack": f"evidence/dev_full/run_control/{upstream_execs['m9h']}/m10_handoff_pack.json",
        "m9_phase_budget_envelope": f"evidence/dev_full/run_control/{upstream_execs['m9i']}/m9_phase_budget_envelope.json",
        "m9_phase_cost_outcome_receipt": f"evidence/dev_full/run_control/{upstream_execs['m9i']}/m9_phase_cost_outcome_receipt.json",
    }

    contract_matrix: list[dict[str, Any]] = []
    for alias, key in contract_artifacts.items():
        row = {"artifact": alias, "s3_key": key, "readable": False, "error": None}
        try:
            s3.head_object(Bucket=evidence_bucket, Key=key)
            row["readable"] = True
        except (BotoCoreError, ClientError) as exc:
            row["error"] = type(exc).__name__
            read_errors.append(f"{alias}:{type(exc).__name__}:{key}")
        contract_matrix.append(row)
    if any(not bool(row["readable"]) for row in contract_matrix):
        blockers.append({"code": "M9-B10", "message": "Required M9 contract artifacts are missing/unreadable."})

    phase_start = min(upstream_times).isoformat().replace("+00:00", "Z") if upstream_times else captured_at

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    verdict = "ADVANCE_TO_M10" if overall_pass else "HOLD_REMEDIATE"
    next_gate = "M10_READY" if overall_pass else "HOLD_REMEDIATE"

    contract_upstream_required_count = len(summary_specs) + len(contract_artifacts)
    contract_upstream_readable_count = sum(1 for row in summary_matrix if bool(row["readable"])) + sum(
        1 for row in contract_matrix if bool(row["readable"])
    )
    contract_output_required_count = 1
    contract_output_published_count = 0
    contract_total_required_count = contract_upstream_required_count + contract_output_required_count

    run_control_prefix = f"evidence/dev_full/run_control/{execution_id}"
    durable_keys = {
        "m9_execution_summary_key": f"{run_control_prefix}/m9_execution_summary.json",
        "m9j_blocker_register_key": f"{run_control_prefix}/m9j_blocker_register.json",
        "m9j_execution_summary_key": f"{run_control_prefix}/m9j_execution_summary.json",
    }

    m9_contract_parity = {
        "required_artifact_count_total": contract_total_required_count,
        "required_upstream_artifact_count": contract_upstream_required_count,
        "readable_upstream_artifact_count": contract_upstream_readable_count,
        "required_m9j_output_count": contract_output_required_count,
        "published_m9j_output_count": contract_output_published_count,
        "all_required_available": bool(
            contract_upstream_readable_count == contract_upstream_required_count
            and contract_output_published_count == contract_output_required_count
        ),
    }

    m9_execution_summary = {
        "phase": "M9.J",
        "phase_id": "M9",
        "phase_execution_id": execution_id,
        "captured_at_utc": captured_at,
        "window_start_utc": phase_start,
        "window_end_utc": captured_at,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "overall_pass": overall_pass,
        "blockers": blockers,
        "blocker_count": len(blockers),
        "verdict": verdict,
        "next_gate": next_gate,
        "p12_verdict": m9h_verdict,
        "p12_verdict_ref": f"evidence/dev_full/run_control/{upstream_execs['m9h']}/m9h_p12_gate_verdict.json",
        "m10_handoff_ref": f"evidence/dev_full/run_control/{upstream_execs['m9h']}/m10_handoff_pack.json",
        "upstream_refs": {
            "m9a_execution_id": upstream_execs["m9a"],
            "m9b_execution_id": upstream_execs["m9b"],
            "m9c_execution_id": upstream_execs["m9c"],
            "m9d_execution_id": upstream_execs["m9d"],
            "m9e_execution_id": upstream_execs["m9e"],
            "m9f_execution_id": upstream_execs["m9f"],
            "m9g_execution_id": upstream_execs["m9g"],
            "m9h_execution_id": upstream_execs["m9h"],
            "m9i_execution_id": upstream_execs["m9i"],
        },
        "m9_contract_parity": m9_contract_parity,
        "durable_artifacts": durable_keys,
    }

    m9j_blocker_register = {
        "captured_at_utc": captured_at,
        "phase": "M9.J",
        "phase_id": "M9",
        "execution_id": execution_id,
        "platform_run_id": platform_run_id,
        "scenario_run_id": scenario_run_id,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "summary_matrix": summary_matrix,
        "contract_matrix": contract_matrix,
        "read_errors": read_errors,
    }

    m9j_execution_summary = {
        "captured_at_utc": captured_at,
        "phase": "M9.J",
        "phase_id": "M9",
        "execution_id": execution_id,
        "overall_pass": overall_pass,
        "blocker_count": len(blockers),
        "verdict": verdict,
        "next_gate": next_gate,
    }

    artifacts = {
        "m9_execution_summary.json": m9_execution_summary,
        "m9j_blocker_register.json": m9j_blocker_register,
        "m9j_execution_summary.json": m9j_execution_summary,
    }
    write_local_artifacts(run_dir, artifacts)

    for name, payload in artifacts.items():
        key = f"{run_control_prefix}/{name}"
        try:
            s3_put_json(s3, evidence_bucket, key, payload)
            if name == "m9_execution_summary.json":
                contract_output_published_count += 1
        except (BotoCoreError, ClientError, ValueError) as exc:
            upload_errors.append(f"{name}:{type(exc).__name__}:{key}")

    if upload_errors:
        blockers = list(blockers)
        blockers.append({"code": "M9-B11", "message": "Failed to publish/readback M9.J artifact set."})
        blockers = dedupe_blockers(blockers)
        overall_pass = False
        verdict = "HOLD_REMEDIATE"
        next_gate = "HOLD_REMEDIATE"

    m9_contract_parity["published_m9j_output_count"] = contract_output_published_count
    m9_contract_parity["all_required_available"] = bool(
        contract_upstream_readable_count == contract_upstream_required_count
        and contract_output_published_count == contract_output_required_count
    )
    if not m9_contract_parity["all_required_available"]:
        blockers = list(blockers)
        blockers.append({"code": "M9-B10", "message": "M9 artifact contract parity is incomplete after M9.J publication."})
        blockers = dedupe_blockers(blockers)
        overall_pass = False
        verdict = "HOLD_REMEDIATE"
        next_gate = "HOLD_REMEDIATE"

    m9_execution_summary["overall_pass"] = overall_pass
    m9_execution_summary["blockers"] = blockers
    m9_execution_summary["blocker_count"] = len(blockers)
    m9_execution_summary["verdict"] = verdict
    m9_execution_summary["next_gate"] = next_gate
    m9_execution_summary["m9_contract_parity"] = m9_contract_parity
    m9j_blocker_register["blockers"] = blockers
    m9j_blocker_register["blocker_count"] = len(blockers)
    m9j_blocker_register["upload_errors"] = upload_errors
    m9j_execution_summary["overall_pass"] = overall_pass
    m9j_execution_summary["blocker_count"] = len(blockers)
    m9j_execution_summary["verdict"] = verdict
    m9j_execution_summary["next_gate"] = next_gate

    artifacts["m9_execution_summary.json"] = m9_execution_summary
    artifacts["m9j_blocker_register.json"] = m9j_blocker_register
    artifacts["m9j_execution_summary.json"] = m9j_execution_summary
    write_local_artifacts(run_dir, artifacts)

    out = {
        "execution_id": execution_id,
        "overall_pass": m9j_execution_summary["overall_pass"],
        "blocker_count": m9j_execution_summary["blocker_count"],
        "verdict": m9j_execution_summary["verdict"],
        "next_gate": m9j_execution_summary["next_gate"],
        "m9_contract_parity": m9_contract_parity,
        "run_dir": str(run_dir),
        "run_control_prefix": f"s3://{evidence_bucket}/{run_control_prefix}/",
    }
    print(json.dumps(out, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
