#!/usr/bin/env python3
"""Materialize PR3-S4 dependency degrade drill evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def run(cmd: list[str], *, timeout: int = 300, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
    if check and proc.returncode != 0:
        raise RuntimeError(f"command_failed:{' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def snap_component(snapshot: dict[str, Any], component: str) -> dict[str, Any]:
    return dict((((snapshot.get("components") or {}).get(component) or {}).get("summary")) or {})


def main() -> None:
    ap = argparse.ArgumentParser(description="PR3-S4 dependency degrade drill")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr3-execution-id", required=True)
    ap.add_argument("--state-id", default="S4")
    ap.add_argument("--artifact-prefix", default="g3a_correctness")
    ap.add_argument("--namespace", required=True)
    ap.add_argument("--platform-run-id", required=True)
    ap.add_argument("--profile-path", required=True)
    ap.add_argument("--deployment", default="fp-pr3-ofp")
    ap.add_argument("--recovery-timeout-seconds", type=int, default=300)
    ap.add_argument("--settle-seconds", type=int, default=30)
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.pr3_execution_id
    manifest = load_json(root / f"{str(args.artifact_prefix).strip()}_wsp_runtime_manifest.json")
    platform_run_id = str(args.platform_run_id).strip()

    drill_started_utc = now_utc()
    run(["kubectl", "scale", f"deployment/{args.deployment}", "-n", args.namespace, "--replicas=0"], timeout=120)
    time.sleep(max(10, int(args.settle_seconds)))
    run(
        [
            "python",
            "scripts/dev_substrate/pr3_runtime_surface_snapshot.py",
            "--pr3-execution-id",
            args.pr3_execution_id,
            "--state-id",
            args.state_id,
            "--snapshot-label",
            "dependency_degrade",
            "--namespace",
            args.namespace,
            "--platform-run-id",
            platform_run_id,
        ],
        timeout=300,
    )
    degrade_snapshot = load_json(root / "g3a_s4_component_snapshot_dependency_degrade.json")

    recover_started_utc = now_utc()
    run(["kubectl", "scale", f"deployment/{args.deployment}", "-n", args.namespace, "--replicas=1"], timeout=120)
    run(
        ["kubectl", "rollout", "status", f"deployment/{args.deployment}", "-n", args.namespace, f"--timeout={args.recovery_timeout_seconds}s"],
        timeout=args.recovery_timeout_seconds + 30,
    )
    run(
        [
            "python",
            "scripts/dev_substrate/pr3_runtime_warm_gate.py",
            "--pr3-execution-id",
            args.pr3_execution_id,
            "--state-id",
            args.state_id,
            "--namespace",
            args.namespace,
            "--platform-run-id",
            platform_run_id,
            "--profile-path",
            args.profile_path,
            "--settle-seconds",
            str(args.settle_seconds),
        ],
        timeout=600,
    )
    run(
        [
            "python",
            "scripts/dev_substrate/pr3_runtime_surface_snapshot.py",
            "--pr3-execution-id",
            args.pr3_execution_id,
            "--state-id",
            args.state_id,
            "--snapshot-label",
            "dependency_recovered",
            "--namespace",
            args.namespace,
            "--platform-run-id",
            platform_run_id,
        ],
        timeout=300,
    )
    recovered_snapshot = load_json(root / "g3a_s4_component_snapshot_dependency_recovered.json")

    degrade_ofp = snap_component(degrade_snapshot, "ofp")
    degrade_dl = snap_component(degrade_snapshot, "dl")
    recovered_ofp = snap_component(recovered_snapshot, "ofp")
    recovered_dl = snap_component(recovered_snapshot, "dl")
    recovery_seconds = (parse_utc(now_utc()) - parse_utc(recover_started_utc)).total_seconds()

    degrade_detected = (
        str(degrade_ofp.get("health_state") or "").upper() in {"RED", "FAILED", "UNHEALTHY", "UNKNOWN"}
        or bool(degrade_ofp.get("__missing__"))
        or str(degrade_dl.get("decision_mode") or "").upper() in {"FAIL_CLOSED", "DEGRADE"}
        or str(degrade_dl.get("health_state") or "").upper() in {"RED", "FAILED", "UNHEALTHY", "UNKNOWN"}
    )
    recovered_ok = (
        str(recovered_ofp.get("health_state") or "").upper() in {"GREEN", "AMBER"}
        and str(recovered_dl.get("health_state") or "").upper() in {"GREEN", "AMBER"}
        and recovery_seconds <= float(args.recovery_timeout_seconds)
    )
    overall_pass = degrade_detected and recovered_ok

    payload = {
        "drill_id": "dependency_degrade",
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": platform_run_id,
        "scenario": f"Scale {args.deployment} to zero after bounded correctness, verify degrade is visible, restore and recover within bound.",
        "expected_behavior": "Dependency loss becomes visible on runtime surfaces and the lane recovers cleanly after restore.",
        "observed_outcome": {
            "degrade_started_utc": drill_started_utc,
            "recover_started_utc": recover_started_utc,
            "recovery_seconds": recovery_seconds,
            "dependency_component": args.deployment,
            "degrade_ofp": degrade_ofp,
            "degrade_dl": degrade_dl,
            "recovered_ofp": recovered_ofp,
            "recovered_dl": recovered_dl,
            "manifest_platform_run_id": str((((manifest.get("identity") or {}).get("platform_run_id")) or "")).strip(),
        },
        "overall_pass": overall_pass,
        "blocker_ids": [] if overall_pass else ["PR3.S4.B26_DEPENDENCY_DRILL_UNEXECUTED"],
    }
    dump_json(root / "g3a_drill_dependency_degrade.json", payload)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
