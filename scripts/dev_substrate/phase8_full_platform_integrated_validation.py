#!/usr/bin/env python3
"""Execute the bounded Phase 8 full-platform integrated validation on live dev_full surfaces."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"


def child_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = str(env.get("PYTHONPATH") or "").strip()
    roots = os.pathsep.join([str(SRC_ROOT), str(REPO_ROOT)])
    env["PYTHONPATH"] = roots if not existing else roots + os.pathsep + existing
    return env


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_cmd(args: list[str]) -> None:
    subprocess.run([sys.executable, *args], check=True, env=child_env())


def archive_copy(src: Path, dest: Path) -> None:
    if not src.exists():
        raise RuntimeError(f"phase8_expected_artifact_missing:{src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)


def fresh_execution_id() -> str:
    return f"phase8_full_platform_integrated_{utc_stamp()}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Execute Phase 8 full-platform integrated validation")
    ap.add_argument("--execution-id", default="")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    ap.add_argument("--aws-region", default="eu-west-2")
    ap.add_argument("--source-execution-id", default="phase4_case_label_coupled_20260312T003302Z")
    ap.add_argument("--phase5-execution-id", default="phase5_learning_managed_20260312T071600Z")
    ap.add_argument("--namespace", default="fraud-platform-rtdl")
    ap.add_argument("--case-labels-namespace", default="fraud-platform-case-labels")
    ap.add_argument("--cluster-name", default="fraud-platform-dev-full")
    ap.add_argument("--nodegroup-name", default="fraud-platform-dev-full-m6f-workers")
    args = ap.parse_args()

    execution_id = str(args.execution_id).strip() or fresh_execution_id()
    stamp = execution_id.rsplit("_", 1)[-1]
    phase6_execution_id = f"phase6_learning_coupled_{stamp}"

    run_control_root = Path(args.run_control_root)
    root = run_control_root / execution_id
    root.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "phase": "PHASE8",
        "generated_at_utc": now_utc(),
        "execution_id": execution_id,
        "phase6_execution_id": phase6_execution_id,
        "source_execution_id": args.source_execution_id,
        "phase5_execution_id": args.phase5_execution_id,
        "steps": [],
    }
    dump_json(root / "phase8_run_manifest.json", manifest)

    run_cmd(
        [
            "scripts/dev_substrate/phase6_learning_coupled_readiness.py",
            "--execution-id",
            phase6_execution_id,
            "--run-control-root",
            args.run_control_root,
            "--aws-region",
            args.aws_region,
            "--namespace",
            args.namespace,
            "--case-labels-namespace",
            args.case_labels_namespace,
            "--source-execution-id",
            args.source_execution_id,
            "--phase5-execution-id",
            args.phase5_execution_id,
            "--cluster-name",
            args.cluster_name,
            "--nodegroup-name",
            args.nodegroup_name,
        ]
    )
    manifest["steps"].append({"step": "phase6_backbone", "execution_id": phase6_execution_id, "completed_at_utc": now_utc()})
    dump_json(root / "phase8_run_manifest.json", manifest)

    source_root = run_control_root / phase6_execution_id
    phase6_summary = load_json(source_root / "phase6_learning_coupled_summary.json")
    platform_run_id = str(phase6_summary.get("platform_run_id") or "").strip()

    phase6_archive_root = root / "phase6_authority"
    for name in (
        "phase6_learning_coupled_receipt.json",
        "phase6_learning_coupled_summary.json",
        "phase6_coupled_scorecard.json",
        "phase6_registry_surface_manifest.json",
        "phase6_coupled_envelope_summary.json",
        "phase6_coupled_timing_probe.json",
        "phase6_candidate_bundle_probe.json",
        "phase6_rollback_bundle_probe.json",
        "phase6_restore_bundle_probe.json",
    ):
        archive_copy(source_root / name, phase6_archive_root / name)

    run_cmd(
        [
            "scripts/dev_substrate/phase7_alert_runbook_drill.py",
            "--execution-id",
            execution_id,
            "--run-control-root",
            args.run_control_root,
            "--aws-region",
            args.aws_region,
        ]
    )
    manifest["steps"].append({"step": "phase7_alert_runbook_drill", "completed_at_utc": now_utc()})
    dump_json(root / "phase8_run_manifest.json", manifest)

    run_cmd(
        [
            "scripts/dev_substrate/phase7_ml_day2_operator_surface.py",
            "--execution-id",
            execution_id,
            "--run-control-root",
            args.run_control_root,
            "--source-phase6-execution-id",
            phase6_execution_id,
            "--aws-region",
            args.aws_region,
            "--rtdl-namespace",
            args.namespace,
        ]
    )
    manifest["steps"].append({"step": "phase7_ml_day2_operator_surface", "completed_at_utc": now_utc()})
    dump_json(root / "phase8_run_manifest.json", manifest)

    run_cmd(
        [
            "scripts/dev_substrate/phase7_idle_restart_drill.py",
            "--execution-id",
            execution_id,
            "--run-control-root",
            args.run_control_root,
            "--aws-region",
            args.aws_region,
            "--cluster-name",
            args.cluster_name,
            "--nodegroup-name",
            args.nodegroup_name,
            "--rtdl-namespace",
            args.namespace,
            "--case-labels-namespace",
            args.case_labels_namespace,
        ]
    )
    manifest["steps"].append({"step": "phase7_idle_restart_drill", "completed_at_utc": now_utc()})
    dump_json(root / "phase8_run_manifest.json", manifest)

    run_cmd(
        [
            "scripts/dev_substrate/phase7_ops_gov_meta_readiness.py",
            "--execution-id",
            execution_id,
            "--run-control-root",
            args.run_control_root,
            "--source-phase6-execution-id",
            phase6_execution_id,
            "--source-platform-run-id",
            platform_run_id,
            "--aws-region",
            args.aws_region,
            "--rtdl-namespace",
            args.namespace,
        ]
    )
    manifest["steps"].append({"step": "phase7_ops_gov_meta_readiness", "completed_at_utc": now_utc()})
    dump_json(root / "phase8_run_manifest.json", manifest)

    run_cmd(
        [
            "scripts/dev_substrate/phase8_integrated_rollup.py",
            "--execution-id",
            execution_id,
            "--run-control-root",
            args.run_control_root,
            "--source-phase6-execution-id",
            phase6_execution_id,
            "--source-platform-run-id",
            platform_run_id,
        ]
    )
    manifest["steps"].append({"step": "phase8_integrated_rollup", "completed_at_utc": now_utc()})
    manifest["platform_run_id"] = platform_run_id
    dump_json(root / "phase8_run_manifest.json", manifest)


if __name__ == "__main__":
    main()
