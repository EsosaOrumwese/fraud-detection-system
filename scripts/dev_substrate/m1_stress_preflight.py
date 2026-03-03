#!/usr/bin/env python3
"""M1 Stage-B local preflight checks for stress program.

Checks:
1. docker_context_lint
2. entrypoint_help_matrix
3. provenance_contract_lint
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HANDLES_PATH = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
DOCKERFILE_PATH = Path("Dockerfile")
DOCKERIGNORE_PATH = Path(".dockerignore")


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ts_token() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _is_placeholder(value: Any) -> bool:
    s = str(value).strip().lower()
    return (
        s in {"", "tbd", "todo", "none", "null"}
        or "to_pin" in s
        or "placeholder" in s
        or s.startswith("<")
    )


def _parse_handles(path: Path) -> dict[str, Any]:
    # Accept optional trailing prose after the closing backtick so annotated
    # handle lines remain machine-parseable.
    rx = re.compile(r"^\* `([^`]+)\s*=\s*([^`]+)`(?:\s.*)?$")
    out: dict[str, Any] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        match = rx.match(line)
        if not match:
            continue
        key = match.group(1).strip()
        val_raw = match.group(2).strip()
        if val_raw.startswith('"') and val_raw.endswith('"'):
            out[key] = val_raw[1:-1]
            continue
        if val_raw.lower() == "true":
            out[key] = True
            continue
        if val_raw.lower() == "false":
            out[key] = False
            continue
        try:
            out[key] = int(val_raw) if "." not in val_raw else float(val_raw)
        except ValueError:
            out[key] = val_raw
    return out


@dataclass(frozen=True)
class CmdCheck:
    name: str
    argv: list[str]


def _entrypoint_checks() -> list[CmdCheck]:
    py = sys.executable
    return [
        CmdCheck("oracle_stream_sort", [py, "-m", "fraud_detection.oracle_store.stream_sort_cli", "--help"]),
        CmdCheck("oracle_checker", [py, "-m", "fraud_detection.oracle_store.cli", "--help"]),
        CmdCheck("scenario_runner", [py, "-m", "fraud_detection.scenario_runner.cli", "run", "--help"]),
        CmdCheck("wsp", [py, "-m", "fraud_detection.world_streamer_producer.cli", "--help"]),
        CmdCheck("ig_service", [py, "-m", "fraud_detection.ingestion_gate.service", "--help"]),
        CmdCheck("archive_writer", [py, "-m", "fraud_detection.archive_writer.worker", "--help"]),
        CmdCheck("ieg_service", [py, "-m", "fraud_detection.identity_entity_graph.service", "--help"]),
        CmdCheck("ofp_projector", [py, "-m", "fraud_detection.online_feature_plane.projector", "--help"]),
        CmdCheck("csfb_intake", [py, "-m", "fraud_detection.context_store_flow_binding.intake", "--help"]),
        CmdCheck("dl_worker", [py, "-m", "fraud_detection.degrade_ladder.worker", "--help"]),
        CmdCheck("df_worker", [py, "-m", "fraud_detection.decision_fabric.worker", "--help"]),
        CmdCheck("al_worker", [py, "-m", "fraud_detection.action_layer.worker", "--help"]),
        CmdCheck("dla_worker", [py, "-m", "fraud_detection.decision_log_audit.worker", "--help"]),
        CmdCheck("case_trigger_worker", [py, "-m", "fraud_detection.case_trigger.worker", "--help"]),
        CmdCheck("cm_worker", [py, "-m", "fraud_detection.case_mgmt.worker", "--help"]),
        CmdCheck("ls_worker", [py, "-m", "fraud_detection.label_store.worker", "--help"]),
        CmdCheck("env_conformance_worker", [py, "-m", "fraud_detection.platform_conformance.worker", "--help"]),
        CmdCheck("reporter_worker", [py, "-m", "fraud_detection.platform_reporter.worker", "--help"]),
        CmdCheck("ofs_runner", [py, "-m", "fraud_detection.offline_feature_plane.worker", "run", "--help"]),
        CmdCheck("mf_runner", [py, "-m", "fraud_detection.model_factory.worker", "run", "--help"]),
        CmdCheck("mpr_runner", [py, "-m", "fraud_detection.learning_registry.worker", "run", "--help"]),
    ]


def _docker_context_lint() -> tuple[dict[str, Any], list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    report: dict[str, Any] = {
        "status": "PASS",
        "dockerfile_exists": DOCKERFILE_PATH.exists(),
        "dockerignore_exists": DOCKERIGNORE_PATH.exists(),
        "forbidden_copy_patterns": [],
        "required_copy_paths_missing": [],
        "dockerignore_required_missing": [],
    }
    if not DOCKERFILE_PATH.exists():
        blockers.append({"code": "M1-ST-B3", "message": "Dockerfile missing."})
        report["status"] = "FAIL"
        return report, blockers

    docker_lines = DOCKERFILE_PATH.read_text(encoding="utf-8").splitlines()
    forbidden_patterns = []
    for idx, line in enumerate(docker_lines, start=1):
        normalized = " ".join(line.strip().split())
        upper = normalized.upper()
        if upper.startswith("COPY . ") or upper == "COPY . .":
            forbidden_patterns.append({"line": idx, "value": line.strip()})
        if upper.startswith("ADD . "):
            forbidden_patterns.append({"line": idx, "value": line.strip()})
    report["forbidden_copy_patterns"] = forbidden_patterns
    if forbidden_patterns:
        blockers.append({"code": "M1-ST-B3", "message": "Forbidden broad Docker context copy detected."})

    required_copy_paths = [
        "pyproject.toml",
        "requirements/m1-image.lock.txt",
        "src/fraud_detection",
        "config/platform",
        "docs/model_spec/platform/contracts",
    ]
    missing_copy = []
    docker_text = "\n".join(docker_lines)
    for item in required_copy_paths:
        if item not in docker_text:
            missing_copy.append(item)
    report["required_copy_paths_missing"] = missing_copy
    if missing_copy:
        blockers.append({"code": "M1-ST-B3", "message": f"Required Docker COPY paths missing: {missing_copy}"})

    if DOCKERIGNORE_PATH.exists():
        ignore_text = DOCKERIGNORE_PATH.read_text(encoding="utf-8")
    else:
        ignore_text = ""
    ignore_tokens = [
        line.strip()
        for line in ignore_text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    default_deny_detected = any(token in {"*", "**"} for token in ignore_tokens)
    report["dockerignore_default_deny_detected"] = default_deny_detected
    required_ignore_patterns = ["runs/", ".env", ".git/", "__pycache__/"]
    missing_ignore = [] if default_deny_detected else [p for p in required_ignore_patterns if p not in ignore_text]
    report["dockerignore_required_missing"] = missing_ignore
    if missing_ignore:
        blockers.append(
            {
                "code": "M1-ST-B3",
                "message": f"Required .dockerignore patterns missing: {missing_ignore}",
            }
        )
    required_allowlist_reopens = ["!requirements", "!requirements/m1-image.lock.txt"]
    missing_allowlist_reopens = (
        [token for token in required_allowlist_reopens if token not in ignore_tokens]
        if default_deny_detected
        else []
    )
    report["dockerignore_required_allowlist_missing"] = missing_allowlist_reopens
    if missing_allowlist_reopens:
        blockers.append(
            {
                "code": "M1-ST-B3",
                "message": (
                    "Default-deny .dockerignore missing required allowlist reopen tokens: "
                    f"{missing_allowlist_reopens}"
                ),
            }
        )

    if blockers:
        report["status"] = "FAIL"
    return report, blockers


def _entrypoint_help_matrix(timeout_seconds: int) -> tuple[dict[str, Any], list[dict[str, str]]]:
    checks = _entrypoint_checks()
    results: list[dict[str, Any]] = []
    blockers: list[dict[str, str]] = []
    base_env = dict(os.environ)
    existing = base_env.get("PYTHONPATH", "")
    src_value = "src"
    if existing.strip():
        if src_value not in [p.strip() for p in existing.split(os.pathsep) if p.strip()]:
            base_env["PYTHONPATH"] = f"{src_value}{os.pathsep}{existing}"
    else:
        base_env["PYTHONPATH"] = src_value

    for check in checks:
        started = _now_utc()
        try:
            proc = subprocess.run(
                check.argv,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=base_env,
            )
            rc = int(proc.returncode)
            stderr = (proc.stderr or "").strip()
            stdout = (proc.stdout or "").strip()
            result = {
                "name": check.name,
                "argv": check.argv,
                "started_at_utc": started,
                "returncode": rc,
                "status": "PASS" if rc == 0 else "FAIL",
                "stdout_head": stdout[:400],
                "stderr_head": stderr[:400],
            }
            if rc != 0:
                blockers.append(
                    {
                        "code": "M1-ST-B4",
                        "message": f"Entrypoint help check failed: {check.name}",
                    }
                )
        except subprocess.TimeoutExpired:
            result = {
                "name": check.name,
                "argv": check.argv,
                "started_at_utc": started,
                "returncode": None,
                "status": "FAIL",
                "stdout_head": "",
                "stderr_head": f"timeout>{timeout_seconds}s",
            }
            blockers.append(
                {
                    "code": "M1-ST-B4",
                    "message": f"Entrypoint help check timed out: {check.name}",
                }
            )
        results.append(result)

    report = {
        "status": "PASS" if not blockers else "FAIL",
        "total_checks": len(results),
        "pass_count": sum(1 for row in results if row["status"] == "PASS"),
        "fail_count": sum(1 for row in results if row["status"] == "FAIL"),
        "checks": results,
    }
    return report, blockers


def _provenance_contract_lint(handles: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    required_keys = [
        "ECR_REPO_URI",
        "IMAGE_TAG_GIT_SHA_PATTERN",
        "IMAGE_REFERENCE_MODE",
        "IMAGE_BUILD_DRIVER",
        "IMAGE_BUILD_CONTEXT_PATH",
        "IMAGE_DOCKERFILE_PATH",
        "SECRETS_BACKEND",
        "SECRETS_PLAINTEXT_OUTPUT_ALLOWED",
    ]
    missing_keys = [key for key in required_keys if key not in handles]
    placeholder_keys = [key for key in required_keys if key in handles and _is_placeholder(handles[key])]

    if missing_keys:
        blockers.append({"code": "M1-ST-B5", "message": f"Required handles missing: {missing_keys}"})
    if placeholder_keys:
        blockers.append({"code": "M1-ST-B5", "message": f"Required handles placeholder-valued: {placeholder_keys}"})

    image_reference_mode = str(handles.get("IMAGE_REFERENCE_MODE", "")).strip()
    if image_reference_mode != "immutable_preferred":
        blockers.append({"code": "M1-ST-B5", "message": "IMAGE_REFERENCE_MODE is not immutable_preferred."})
    if str(handles.get("IMAGE_BUILD_CONTEXT_PATH", "")).strip() != ".":
        blockers.append({"code": "M1-ST-B5", "message": "IMAGE_BUILD_CONTEXT_PATH must remain '.' for current contract."})
    if str(handles.get("IMAGE_BUILD_DRIVER", "")).strip() != "github_actions":
        blockers.append({"code": "M1-ST-B5", "message": "IMAGE_BUILD_DRIVER is not github_actions."})
    if str(handles.get("SECRETS_BACKEND", "")).strip() != "ssm_and_secrets_manager":
        blockers.append({"code": "M1-ST-B5", "message": "SECRETS_BACKEND is not ssm_and_secrets_manager."})
    if bool(handles.get("SECRETS_PLAINTEXT_OUTPUT_ALLOWED", True)):
        blockers.append({"code": "M1-ST-B5", "message": "SECRETS_PLAINTEXT_OUTPUT_ALLOWED must be false."})

    report = {
        "status": "PASS" if not blockers else "FAIL",
        "required_keys_checked": required_keys,
        "missing_keys": missing_keys,
        "placeholder_keys": placeholder_keys,
        "values": {
            "ECR_REPO_URI": handles.get("ECR_REPO_URI"),
            "IMAGE_TAG_GIT_SHA_PATTERN": handles.get("IMAGE_TAG_GIT_SHA_PATTERN"),
            "IMAGE_REFERENCE_MODE": handles.get("IMAGE_REFERENCE_MODE"),
            "IMAGE_BUILD_DRIVER": handles.get("IMAGE_BUILD_DRIVER"),
            "IMAGE_BUILD_CONTEXT_PATH": handles.get("IMAGE_BUILD_CONTEXT_PATH"),
            "IMAGE_DOCKERFILE_PATH": handles.get("IMAGE_DOCKERFILE_PATH"),
            "SECRETS_BACKEND": handles.get("SECRETS_BACKEND"),
            "SECRETS_PLAINTEXT_OUTPUT_ALLOWED": handles.get("SECRETS_PLAINTEXT_OUTPUT_ALLOWED"),
        },
    }
    return report, blockers


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _unique_blockers(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, str]] = []
    for row in items:
        code = str(row.get("code", "")).strip()
        msg = str(row.get("message", "")).strip()
        key = (code, msg)
        if key in seen:
            continue
        seen.add(key)
        out.append({"code": code, "message": msg})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="M1 stress local preflight runner")
    parser.add_argument("--phase-id", default="M1")
    parser.add_argument("--phase-execution-id", default=f"m1_stress_preflight_{_ts_token()}")
    parser.add_argument("--output-root", default="runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")
    parser.add_argument("--entrypoint-timeout-seconds", type=int, default=45)
    args = parser.parse_args()

    if not HANDLES_PATH.exists():
        raise SystemExit(f"Handles file not found: {HANDLES_PATH}")

    phase_execution_id = str(args.phase_execution_id).strip()
    phase_id = str(args.phase_id).strip() or "M1"
    output_dir = Path(args.output_root) / phase_execution_id / "stress"
    output_dir.mkdir(parents=True, exist_ok=True)

    handles = _parse_handles(HANDLES_PATH)

    docker_report, docker_blockers = _docker_context_lint()
    entrypoint_report, entrypoint_blockers = _entrypoint_help_matrix(args.entrypoint_timeout_seconds)
    provenance_report, provenance_blockers = _provenance_contract_lint(handles)

    blockers = _unique_blockers(docker_blockers + entrypoint_blockers + provenance_blockers)
    overall_pass = len(blockers) == 0
    verdict = "READY_FOR_M1_STRESS_WINDOW" if overall_pass else "HOLD_REMEDIATE"

    checks_payload = {
        "phase_id": phase_id,
        "phase_execution_id": phase_execution_id,
        "captured_at_utc": _now_utc(),
        "overall_pass": overall_pass,
        "verdict": verdict,
        "checks": {
            "docker_context_lint": docker_report,
            "entrypoint_help_matrix": entrypoint_report,
            "provenance_contract_lint": provenance_report,
        },
        "blocker_count": len(blockers),
        "blockers": blockers,
    }

    blocker_register = {
        "phase_id": phase_id,
        "phase_execution_id": phase_execution_id,
        "captured_at_utc": _now_utc(),
        "blocker_count": len(blockers),
        "blockers": blockers,
    }

    execution_summary = {
        "phase_id": phase_id,
        "phase_execution_id": phase_execution_id,
        "captured_at_utc": _now_utc(),
        "overall_pass": overall_pass,
        "verdict": verdict,
        "next_gate": "M1_STAGE_B_READY" if overall_pass else "HOLD_REMEDIATE",
        "artifacts": {
            "m1_preflight_checks": str(output_dir / "m1_preflight_checks.json"),
            "m1_blocker_register": str(output_dir / "m1_blocker_register.json"),
            "m1_execution_summary": str(output_dir / "m1_execution_summary.json"),
            "m1_decision_log": str(output_dir / "m1_decision_log.json"),
        },
        "blocker_count": len(blockers),
    }

    decision_log = {
        "phase_id": phase_id,
        "phase_execution_id": phase_execution_id,
        "captured_at_utc": _now_utc(),
        "decisions": [
            {
                "id": "M1-ST-D1",
                "decision": "Run deterministic local preflight before managed packaging stress windows.",
                "rationale": "Shortens feedback loop and reduces avoidable managed-run spend.",
            },
            {
                "id": "M1-ST-D2",
                "decision": "Fail closed when immutable/provenance contract checks fail.",
                "rationale": "Prevents drift into mutable-tag or weak provenance posture.",
            },
        ],
        "overall_pass": overall_pass,
        "verdict": verdict,
    }

    _write_json(output_dir / "m1_preflight_checks.json", checks_payload)
    _write_json(output_dir / "m1_blocker_register.json", blocker_register)
    _write_json(output_dir / "m1_execution_summary.json", execution_summary)
    _write_json(output_dir / "m1_decision_log.json", decision_log)

    print(
        json.dumps(
            {
                "phase_execution_id": phase_execution_id,
                "overall_pass": overall_pass,
                "verdict": verdict,
                "output_dir": str(output_dir),
                "blocker_count": len(blockers),
            },
            ensure_ascii=True,
        )
    )
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
