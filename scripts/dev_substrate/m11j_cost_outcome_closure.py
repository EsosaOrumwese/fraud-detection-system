#!/usr/bin/env python3
"""Dispatch M11.J managed lane and materialize local evidence artifacts."""

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


WORKFLOW_FILE = "dev_full_m11_managed.yml"
DEFAULT_ROLE_ARN = "arn:aws:iam::230372904534:role/GitHubAction-AssumeRoleWithAction"
POLL_INTERVAL_SECONDS = 20
POLL_TIMEOUT_SECONDS = 120 * 60


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
    execution_id = env.get("M11J_EXECUTION_ID", "").strip()
    run_dir_raw = env.get("M11J_RUN_DIR", "").strip()
    evidence_bucket = env.get("EVIDENCE_BUCKET", "").strip()
    upstream_m11i_execution = env.get("UPSTREAM_M11I_EXECUTION", "").strip()
    aws_region = env.get("AWS_REGION", "eu-west-2").strip() or "eu-west-2"
    role_arn = (
        env.get("M11_GHA_ROLE_TO_ASSUME", "").strip()
        or env.get("AWS_ROLE_TO_ASSUME", "").strip()
        or env.get("GHA_OIDC_ROLE_ARN", "").strip()
        or DEFAULT_ROLE_ARN
    )

    if not execution_id:
        raise SystemExit("M11J_EXECUTION_ID is required.")
    if not run_dir_raw:
        raise SystemExit("M11J_RUN_DIR is required.")
    if not evidence_bucket:
        raise SystemExit("EVIDENCE_BUCKET is required.")
    if not upstream_m11i_execution:
        raise SystemExit("UPSTREAM_M11I_EXECUTION is required.")

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
            "m11_subphase=J",
            "-f",
            f"upstream_m11i_execution={upstream_m11i_execution}",
            "-f",
            f"m11j_execution_id={execution_id}",
        ],
        timeout=150,
    )
    if rc != 0:
        blockers.append({"code": "M11-B11", "message": f"M11.J workflow dispatch failed ({err[:140]})."})

    run_id = 0
    run_url = ""
    if rc == 0:
        find_deadline = time.time() + 180
        while time.time() < find_deadline:
            run_id, run_url = find_workflow_run(repo, branch, dispatch_start - timedelta(seconds=120), "M11.J")
            if run_id > 0:
                break
            time.sleep(5)
        if run_id <= 0:
            workflow_advisories.append("M11.J workflow run id not discoverable after dispatch.")

    run_status = ""
    run_conclusion = ""
    if run_id > 0:
        run_status, run_conclusion, url = wait_for_run(repo, run_id, POLL_TIMEOUT_SECONDS)
        if url:
            run_url = url
        if run_status.lower() != "completed" or run_conclusion.lower() != "success":
            workflow_advisories.append(f"M11.J workflow did not report success ({run_status}/{run_conclusion}).")

    s3 = boto3.client("s3", region_name=aws_region)
    budget_key = f"evidence/dev_full/run_control/{execution_id}/m11_phase_budget_envelope.json"
    cost_key = f"evidence/dev_full/run_control/{execution_id}/m11_phase_cost_outcome_receipt.json"
    register_key = f"evidence/dev_full/run_control/{execution_id}/m11j_blocker_register.json"
    summary_key = f"evidence/dev_full/run_control/{execution_id}/m11j_execution_summary.json"
    phase_summary_key = f"evidence/dev_full/run_control/{execution_id}/m11_execution_summary.json"

    budget: dict[str, Any] | None = None
    cost: dict[str, Any] | None = None
    register: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None
    phase_summary: dict[str, Any] | None = None
    for key, target in (
        (budget_key, "budget"),
        (cost_key, "cost"),
        (register_key, "register"),
        (summary_key, "summary"),
        (phase_summary_key, "phase_summary"),
    ):
        try:
            payload = s3_get_json(s3, evidence_bucket, key)
            if target == "budget":
                budget = payload
            elif target == "cost":
                cost = payload
            elif target == "register":
                register = payload
            elif target == "summary":
                summary = payload
            else:
                phase_summary = payload
        except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as exc:
            read_errors.append({"surface": key, "error": type(exc).__name__})
            code = "M11-B12" if target == "phase_summary" else "M11-B11"
            blockers.append({"code": code, "message": f"M11.J artifact unreadable: {target}."})

    if summary is not None:
        if not bool(summary.get("overall_pass")):
            blockers.append({"code": "M11-B11", "message": "M11.J summary overall_pass is false."})
        if str(summary.get("verdict", "")).strip() != "ADVANCE_TO_M12":
            blockers.append({"code": "M11-B11", "message": "M11.J summary verdict is not ADVANCE_TO_M12."})
        if str(summary.get("next_gate", "")).strip() != "M12_READY":
            blockers.append({"code": "M11-B11", "message": "M11.J summary next_gate is not M12_READY."})
        if not bool(summary.get("all_required_available")):
            blockers.append({"code": "M11-B11", "message": "M11.J summary all_required_available is false."})

    if phase_summary is not None:
        if not bool(phase_summary.get("overall_pass")):
            blockers.append({"code": "M11-B12", "message": "M11 phase summary overall_pass is false."})
        if str(phase_summary.get("verdict", "")).strip() != "ADVANCE_TO_M12":
            blockers.append({"code": "M11-B12", "message": "M11 phase summary verdict is not ADVANCE_TO_M12."})
        if str(phase_summary.get("next_gate", "")).strip() != "M12_READY":
            blockers.append({"code": "M11-B12", "message": "M11 phase summary next_gate is not M12_READY."})

    if register and isinstance(register.get("blockers"), list):
        for row in register.get("blockers", []):
            if not isinstance(row, dict):
                continue
            text = " ".join(
                [
                    str(row.get("message", "")),
                    str(row.get("detail", "")),
                    str(row.get("surface", "")),
                ]
            ).lower()
            if any(token in text for token in ("resourcelimit", "quota", "throttl", "accessdenied", "access denied")):
                blockers.append({"code": "M11-B19", "message": "M11.J indicates quota/capacity/access boundary pressure."})
                break

    lane_gate_pass = bool(summary and bool(summary.get("overall_pass")) and str(summary.get("next_gate", "")).strip() == "M12_READY" and str(summary.get("verdict", "")).strip() == "ADVANCE_TO_M12")
    if workflow_advisories:
        if not lane_gate_pass:
            for msg in workflow_advisories:
                blockers.append({"code": "M11-B11", "message": msg})

    blockers = dedupe_blockers(blockers)
    if summary is None:
        summary = {
            "captured_at_utc": captured_at,
            "phase": "M11.J",
            "phase_id": "P15",
            "execution_id": execution_id,
            "overall_pass": False,
            "verdict": "HOLD_REMEDIATE",
            "next_gate": "HOLD_REMEDIATE",
            "blocker_count": len(blockers),
            "all_required_available": False,
        }
    if phase_summary is None:
        phase_summary = {
            "captured_at_utc": captured_at,
            "phase": "M11",
            "phase_id": "P11-P15",
            "execution_id": execution_id,
            "status": "NOT_DONE",
            "overall_pass": False,
            "verdict": "HOLD_REMEDIATE",
            "next_gate": "HOLD_REMEDIATE",
        }
    if register is None:
        register = {
            "captured_at_utc": captured_at,
            "phase": "M11.J",
            "phase_id": "P15",
            "execution_id": execution_id,
            "overall_pass": False,
            "blocker_count": len(blockers),
            "blockers": blockers,
            "read_errors": read_errors,
            "advisories": workflow_advisories,
        }
    if budget is None:
        budget = {
            "captured_at_utc": captured_at,
            "phase": "M11.J",
            "phase_id": "P15",
            "execution_id": execution_id,
            "overall_pass": False,
            "note": "Budget envelope missing from managed output.",
        }
    if cost is None:
        cost = {
            "captured_at_utc": captured_at,
            "phase": "M11.J",
            "phase_id": "P15",
            "phase_execution_id": execution_id,
            "overall_pass": False,
            "note": "Cost outcome receipt missing from managed output.",
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
        summary["verdict"] = "HOLD_REMEDIATE"
        summary["next_gate"] = "HOLD_REMEDIATE"
        summary["blocker_count"] = len(blockers)
        summary["all_required_available"] = False
        phase_summary["overall_pass"] = False
        phase_summary["verdict"] = "HOLD_REMEDIATE"
        phase_summary["next_gate"] = "HOLD_REMEDIATE"
        phase_summary["status"] = "NOT_DONE"

    write_local_artifacts(
        run_dir,
        {
            "m11_phase_budget_envelope.json": budget,
            "m11_phase_cost_outcome_receipt.json": cost,
            "m11j_blocker_register.json": register,
            "m11j_execution_summary.json": summary,
            "m11_execution_summary.json": phase_summary,
        },
    )

    print(
        json.dumps(
            {
                "execution_id": execution_id,
                "overall_pass": bool(summary.get("overall_pass")),
                "blocker_count": int(summary.get("blocker_count", 0) or 0),
                "next_gate": str(summary.get("next_gate", "")),
                "verdict": str(summary.get("verdict", "")),
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
