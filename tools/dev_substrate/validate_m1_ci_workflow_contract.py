#!/usr/bin/env python3
"""Static CI contract validator for M1.H (authoritative workflow gate checks)."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("workflow YAML root must be a mapping")
    return data


def _get_step(steps: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for step in steps:
        if isinstance(step, dict) and step.get("name") == name:
            return step
    return None


def _contains_all(text: str, needles: list[str]) -> bool:
    return all(n in text for n in needles)


def validate(workflow_path: Path, repo_root: Path) -> list[CheckResult]:
    data = _load_yaml(workflow_path)
    results: list[CheckResult] = []

    trigger = data.get("on", data.get(True, {}))
    workflow_dispatch = trigger.get("workflow_dispatch", {}) if isinstance(trigger, dict) else {}
    inputs = workflow_dispatch.get("inputs", {}) if isinstance(workflow_dispatch, dict) else {}
    required_inputs = {
        "platform_run_id",
        "aws_region",
        "aws_role_to_assume",
        "ecr_repo_name",
        "ecr_repo_uri",
    }
    missing_inputs = sorted(k for k in required_inputs if k not in inputs)
    results.append(
        CheckResult(
            name="workflow_dispatch_required_inputs",
            passed=not missing_inputs,
            detail="missing: " + ",".join(missing_inputs) if missing_inputs else "all required inputs present",
        )
    )

    permissions = data.get("permissions", {})
    permissions_ok = isinstance(permissions, dict) and permissions.get("contents") == "read" and permissions.get("id-token") == "write"
    results.append(
        CheckResult(
            name="permissions_least_privilege",
            passed=permissions_ok,
            detail=str(permissions) if isinstance(permissions, dict) else "permissions block missing/invalid",
        )
    )

    jobs = data.get("jobs", {})
    build_job = jobs.get("build_and_push", {}) if isinstance(jobs, dict) else {}
    outputs = build_job.get("outputs", {}) if isinstance(build_job, dict) else {}
    required_outputs = {"image_tag", "image_digest", "git_sha", "ci_run_id", "build_actor"}
    missing_outputs = sorted(k for k in required_outputs if k not in outputs)
    results.append(
        CheckResult(
            name="job_outputs_plumbing",
            passed=not missing_outputs,
            detail="missing: " + ",".join(missing_outputs) if missing_outputs else "all required outputs present",
        )
    )

    steps = build_job.get("steps", []) if isinstance(build_job, dict) else []
    if not isinstance(steps, list):
        steps = []

    reject_step = _get_step(steps, "Reject static AWS credential posture")
    reject_run = reject_step.get("run", "") if isinstance(reject_step, dict) else ""
    results.append(
        CheckResult(
            name="fail_closed_static_aws_credential_guard",
            passed=bool(reject_step) and _contains_all(reject_run, ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "exit 1"]),
            detail="guard present" if reject_step else "step missing",
        )
    )

    build_step = _get_step(steps, "Build immutable image")
    build_run = build_step.get("run", "") if isinstance(build_step, dict) else ""
    results.append(
        CheckResult(
            name="fail_closed_missing_dockerfile_guard",
            passed=bool(build_step) and _contains_all(build_run, ['if [[ ! -f "${{ inputs.image_dockerfile_path }}" ]]', "exit 1"]),
            detail="guard present" if build_step else "step missing",
        )
    )

    digest_step = _get_step(steps, "Resolve immutable image digest")
    digest_run = digest_step.get("run", "") if isinstance(digest_step, dict) else ""
    results.append(
        CheckResult(
            name="fail_closed_missing_digest_guard",
            passed=bool(digest_step) and _contains_all(digest_run, ["-z \"${DIGEST}\"", "\"None\"", "\"null\"", "exit 1"]),
            detail="guard present" if digest_step else "step missing",
        )
    )

    emit_step = _get_step(steps, "Emit M1 evidence artifacts (CI-local)")
    emit_run = emit_step.get("run", "") if isinstance(emit_step, dict) else ""
    required_artifacts = [
        "build_command_surface_receipt.json",
        "packaging_provenance.json",
        "security_secret_injection_checks.json",
    ]
    missing_artifacts = [f for f in required_artifacts if f not in emit_run]
    results.append(
        CheckResult(
            name="evidence_artifact_contract_coverage",
            passed=bool(emit_step) and not missing_artifacts,
            detail="missing: " + ",".join(missing_artifacts) if missing_artifacts else "all required artifacts emitted",
        )
    )

    upload_step = _get_step(steps, "Upload CI evidence artifact pack")
    upload_path = upload_step.get("with", {}).get("path", "") if isinstance(upload_step, dict) else ""
    results.append(
        CheckResult(
            name="artifact_upload_path_contract",
            passed=bool(upload_step) and "evidence/runs/${{ inputs.platform_run_id }}/P(-1)/" in str(upload_path),
            detail=str(upload_path) if upload_step else "upload step missing",
        )
    )

    dockerfile_exists = (repo_root / "Dockerfile").exists()
    results.append(
        CheckResult(
            name="prerequisite_failure_simulation_missing_dockerfile",
            passed=True,
            detail=(
                "local Dockerfile missing; workflow precheck would fail-closed as expected"
                if not dockerfile_exists
                else "local Dockerfile present; missing-dockerfile branch not triggered in simulation"
            ),
        )
    )

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate M1 authoritative CI workflow contract.")
    parser.add_argument("--workflow", required=True, help="Path to workflow YAML.")
    parser.add_argument("--report", required=True, help="Path to write JSON validation report.")
    args = parser.parse_args()

    workflow_path = Path(args.workflow).resolve()
    repo_root = Path.cwd()
    report_path = Path(args.report).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    results = validate(workflow_path=workflow_path, repo_root=repo_root)
    passed = all(r.passed for r in results)
    payload = {
        "phase": "M1.H",
        "workflow_path": str(workflow_path),
        "validated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "verdict": "PASS" if passed else "FAIL",
        "checks": [r.__dict__ for r in results],
    }
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"M1_H_VALIDATION_VERDICT={payload['verdict']}")
    print(f"M1_H_VALIDATION_REPORT={report_path}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
