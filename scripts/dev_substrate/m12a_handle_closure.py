#!/usr/bin/env python3
"""Dispatch M12.A managed lane and materialize local evidence artifacts."""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


WORKFLOW_FILE = "dev_full_m12_managed.yml"
DEFAULT_ROLE_ARN = "arn:aws:iam::230372904534:role/GitHubAction-AssumeRoleWithAction"
POLL_INTERVAL_SECONDS = 20
POLL_TIMEOUT_SECONDS = 90 * 60


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_cmd(argv: list[str], timeout: int = 180) -> tuple[int, str, str]:
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return int(p.returncode), (p.stdout or "").strip(), (p.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def dedupe_blockers(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        code = str(row.get("code", "")).strip()
        message = str(row.get("message", "")).strip()
        sig = (code, message)
        if sig in seen:
            continue
        seen.add(sig)
        out.append({"code": code, "message": message})
    return out


def s3_get_json(s3: Any, bucket: str, key: str) -> dict[str, Any]:
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("json_not_object")
    return payload


def write_local_artifacts(run_dir: Path, artifacts: dict[str, dict[str, Any]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in artifacts.items():
        (run_dir / name).write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def resolve_repo() -> str:
    env_repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if env_repo:
        return env_repo
    rc, out, _ = run_cmd(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"], timeout=60)
    if rc == 0 and out.strip():
        return out.strip()
    return "EsosaOrumwese/fraud-detection-system"


def resolve_branch() -> str:
    rc, out, _ = run_cmd(["git", "branch", "--show-current"], timeout=30)
    if rc == 0 and out.strip():
        return out.strip()
    return "main"


def parse_iso(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def find_workflow_run(repo: str, branch: str, min_created_at: datetime, title_token: str) -> tuple[int, str]:
    rc, out, err = run_cmd(
        [
            "gh",
            "run",
            "list",
            "--repo",
            repo,
            "--workflow",
            WORKFLOW_FILE,
            "--branch",
            branch,
            "--event",
            "workflow_dispatch",
            "--limit",
            "40",
            "--json",
            "databaseId,createdAt,status,conclusion,url,displayTitle",
        ],
        timeout=90,
    )
    if rc != 0:
        return 0, f"run_list_failed:{err[:180]}"
    try:
        rows = json.loads(out)
    except json.JSONDecodeError:
        return 0, "run_list_json_decode_failed"
    if not isinstance(rows, list):
        return 0, "run_list_not_list"
    best_id = 0
    best_created = datetime.min.replace(tzinfo=timezone.utc)
    best_url = ""
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("displayTitle", "")).strip()
        if title_token and title_token.lower() not in title.lower():
            continue
        created_at = str(row.get("createdAt", "")).strip()
        rid = int(row.get("databaseId", 0) or 0)
        if not created_at or rid <= 0:
            continue
        try:
            ts = parse_iso(created_at)
        except Exception:
            continue
        if ts < min_created_at:
            continue
        if ts >= best_created:
            best_created = ts
            best_id = rid
            best_url = str(row.get("url", "")).strip()
    if best_id <= 0:
        return 0, "run_not_found_after_dispatch"
    return best_id, best_url


def wait_for_run(repo: str, run_id: int, timeout_seconds: int) -> tuple[str, str, str]:
    deadline = time.time() + timeout_seconds
    last_status = ""
    last_conclusion = ""
    last_url = ""
    while time.time() < deadline:
        rc, out, _ = run_cmd(
            [
                "gh",
                "run",
                "view",
                str(run_id),
                "--repo",
                repo,
                "--json",
                "status,conclusion,url",
            ],
            timeout=90,
        )
        if rc != 0:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        try:
            payload = json.loads(out)
        except json.JSONDecodeError:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        status = str(payload.get("status", "")).strip()
        conclusion = str(payload.get("conclusion", "")).strip()
        url = str(payload.get("url", "")).strip()
        last_status = status
        last_conclusion = conclusion
        last_url = url
        if status.lower() == "completed":
            return status, conclusion, url
        time.sleep(POLL_INTERVAL_SECONDS)
    return last_status or "timeout", last_conclusion or "timeout", last_url


def main() -> int:
    env = dict(os.environ)
    execution_id = env.get("M12A_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M12A_RUN_DIR", "").strip()
    evidence_bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m11j_execution = env.get("UPSTREAM_M11J_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"
    role_arn = (
        env.get("M12_GHA_ROLE_TO_ASSUME", "").strip()
        or env.get("AWS_ROLE_TO_ASSUME", "").strip()
        or env.get("GHA_OIDC_ROLE_ARN", "").strip()
        or DEFAULT_ROLE_ARN
    )

    upstream_m12a_execution = env.get("M12_UPSTREAM_M12A_EXECUTION", "M12_S0_NOT_APPLICABLE").strip() or "M12_S0_NOT_APPLICABLE"
    upstream_m12b_execution = env.get("M12_UPSTREAM_M12B_EXECUTION", "M12_S0_NOT_APPLICABLE").strip() or "M12_S0_NOT_APPLICABLE"
    upstream_m12c_execution = env.get("M12_UPSTREAM_M12C_EXECUTION", "M12_S0_NOT_APPLICABLE").strip() or "M12_S0_NOT_APPLICABLE"
    upstream_m12d_execution = env.get("M12_UPSTREAM_M12D_EXECUTION", "M12_S0_NOT_APPLICABLE").strip() or "M12_S0_NOT_APPLICABLE"
    upstream_m12e_execution = env.get("M12_UPSTREAM_M12E_EXECUTION", "M12_S0_NOT_APPLICABLE").strip() or "M12_S0_NOT_APPLICABLE"
    upstream_m12f_execution = env.get("M12_UPSTREAM_M12F_EXECUTION", "M12_S0_NOT_APPLICABLE").strip() or "M12_S0_NOT_APPLICABLE"
    upstream_m12g_execution = env.get("M12_UPSTREAM_M12G_EXECUTION", "M12_S0_NOT_APPLICABLE").strip() or "M12_S0_NOT_APPLICABLE"
    upstream_m12h_execution = env.get("M12_UPSTREAM_M12H_EXECUTION", "M12_S0_NOT_APPLICABLE").strip() or "M12_S0_NOT_APPLICABLE"
    upstream_m12i_execution = env.get("M12_UPSTREAM_M12I_EXECUTION", "M12_S0_NOT_APPLICABLE").strip() or "M12_S0_NOT_APPLICABLE"

    if not execution_id:
        raise SystemExit("M12A_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M12A_RUN_DIR is required.")
    if not evidence_bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m11j_execution:
        raise SystemExit("UPSTREAM_M11J_EXECUTION is required.")

    run_dir = Path(run_dir_raw)
    captured_at = now_utc()
    blockers: list[dict[str, str]] = []
    read_errors: list[dict[str, str]] = []
    workflow_advisories: list[str] = []

    repo = resolve_repo()
    branch = resolve_branch()
    dispatch_start = datetime.now(timezone.utc)
    rc, _, err = run_cmd(
        [
            "gh",
            "workflow",
            "run",
            WORKFLOW_FILE,
            "--repo",
            repo,
            "--ref",
            branch,
            "-f",
            f"aws_region={aws_region}",
            "-f",
            f"aws_role_to_assume={role_arn}",
            "-f",
            f"evidence_bucket={evidence_bucket}",
            "-f",
            "m12_subphase=A",
            "-f",
            "execution_mode=m12a_execute",
            "-f",
            f"upstream_m11j_execution={upstream_m11j_execution}",
            "-f",
            f"upstream_m12a_execution={upstream_m12a_execution}",
            "-f",
            f"upstream_m12b_execution={upstream_m12b_execution}",
            "-f",
            f"upstream_m12c_execution={upstream_m12c_execution}",
            "-f",
            f"upstream_m12d_execution={upstream_m12d_execution}",
            "-f",
            f"upstream_m12e_execution={upstream_m12e_execution}",
            "-f",
            f"upstream_m12f_execution={upstream_m12f_execution}",
            "-f",
            f"upstream_m12g_execution={upstream_m12g_execution}",
            "-f",
            f"upstream_m12h_execution={upstream_m12h_execution}",
            "-f",
            f"upstream_m12i_execution={upstream_m12i_execution}",
            "-f",
            f"m12_execution_id={execution_id}",
        ],
        timeout=150,
    )
    if rc != 0:
        blockers.append({"code": "M12-B1", "message": f"M12.A workflow dispatch failed ({err[:140]})."})

    run_id = 0
    run_url = ""
    if rc == 0:
        find_deadline = time.time() + 180
        while time.time() < find_deadline:
            run_id, run_url = find_workflow_run(repo, branch, dispatch_start - timedelta(seconds=120), "M12.A")
            if run_id > 0:
                break
            time.sleep(5)
        if run_id <= 0:
            workflow_advisories.append("M12.A workflow run id not discoverable after dispatch.")

    run_status = ""
    run_conclusion = ""
    if run_id > 0:
        run_status, run_conclusion, url = wait_for_run(repo, run_id, POLL_TIMEOUT_SECONDS)
        if url:
            run_url = url
        if run_status.lower() != "completed" or run_conclusion.lower() != "success":
            workflow_advisories.append(f"M12.A workflow did not report success ({run_status}/{run_conclusion}).")

    s3 = boto3.client("s3", region_name=aws_region)
    snapshot_key = f"evidence/dev_full/run_control/{execution_id}/m12a_handle_closure_snapshot.json"
    register_key = f"evidence/dev_full/run_control/{execution_id}/m12a_blocker_register.json"
    summary_key = f"evidence/dev_full/run_control/{execution_id}/m12a_execution_summary.json"

    snapshot: dict[str, Any] | None = None
    register: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None
    for key, target in (
        (snapshot_key, "snapshot"),
        (register_key, "register"),
        (summary_key, "summary"),
    ):
        try:
            payload = s3_get_json(s3, evidence_bucket, key)
            if target == "snapshot":
                snapshot = payload
            elif target == "register":
                register = payload
            else:
                summary = payload
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": key, "error": type(exc).__name__})
            blockers.append({"code": "M12-B1", "message": f"M12.A artifact unreadable: {target}."})

    if summary is not None:
        if not bool(summary.get("overall_pass")):
            blockers.append({"code": "M12-B1", "message": "M12.A summary overall_pass is false."})
        if str(summary.get("next_gate", "")).strip() != "M12.B_READY":
            blockers.append({"code": "M12-B1", "message": "M12.A summary next_gate is not M12.B_READY."})
        if str(summary.get("verdict", "")).strip() != "ADVANCE_TO_M12_B":
            blockers.append({"code": "M12-B1", "message": "M12.A summary verdict is not ADVANCE_TO_M12_B."})

    lane_gate_pass = bool(
        summary
        and bool(summary.get("overall_pass"))
        and str(summary.get("next_gate", "")).strip() == "M12.B_READY"
        and str(summary.get("verdict", "")).strip() == "ADVANCE_TO_M12_B"
    )
    if workflow_advisories:
        if not lane_gate_pass:
            for msg in workflow_advisories:
                blockers.append({"code": "M12-B1", "message": msg})

    blockers = dedupe_blockers(blockers)
    if summary is None:
        summary = {
            "captured_at_utc": captured_at,
            "phase": "M12.A",
            "phase_id": "P15",
            "execution_id": execution_id,
            "overall_pass": False,
            "next_gate": "HOLD_REMEDIATE",
            "verdict": "HOLD_REMEDIATE",
            "blocker_count": len(blockers),
            "upstream_refs": {"m11j_execution_id": upstream_m11j_execution},
        }
    if register is None:
        register = {
            "captured_at_utc": captured_at,
            "phase": "M12.A",
            "phase_id": "P15",
            "execution_id": execution_id,
            "overall_pass": False,
            "blocker_count": len(blockers),
            "blockers": blockers,
            "read_errors": read_errors,
            "advisories": workflow_advisories,
        }
    if snapshot is None:
        snapshot = {
            "captured_at_utc": captured_at,
            "phase": "M12.A",
            "phase_id": "P15",
            "execution_id": execution_id,
            "overall_pass": False,
            "note": "Handle closure snapshot missing from managed output.",
            "upstream_m11j_execution": upstream_m11j_execution,
        }

    register["workflow_dispatch"] = {
        "repo": repo,
        "branch": branch,
        "run_id": run_id,
        "run_url": run_url,
        "run_status": run_status,
        "run_conclusion": run_conclusion,
        "role_arn": role_arn,
    }
    register["advisories"] = workflow_advisories
    if blockers:
        register["overall_pass"] = False
        register["blocker_count"] = len(blockers)
        register["blockers"] = blockers
        summary["overall_pass"] = False
        summary["next_gate"] = "HOLD_REMEDIATE"
        summary["verdict"] = "HOLD_REMEDIATE"
        summary["blocker_count"] = len(blockers)

    write_local_artifacts(
        run_dir,
        {
            "m12a_handle_closure_snapshot.json": snapshot,
            "m12a_blocker_register.json": register,
            "m12a_execution_summary.json": summary,
        },
    )

    print(
        json.dumps(
            {
                "execution_id": execution_id,
                "overall_pass": bool(summary.get("overall_pass")),
                "blocker_count": int(summary.get("blocker_count", 0) or 0),
                "next_gate": str(summary.get("next_gate", "")),
                "run_dir": run_dir.as_posix(),
                "workflow_run_id": run_id,
                "workflow_run_url": run_url,
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
