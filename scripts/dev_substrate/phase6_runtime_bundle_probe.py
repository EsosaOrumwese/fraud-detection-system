#!/usr/bin/env python3
"""Probe live DLA governance stamps for Phase 6 bundle-attribution truth."""

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


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def run(cmd: list[str], *, timeout: int = 180, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
    if check and proc.returncode != 0:
        raise RuntimeError(f"command_failed:{' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def exec_json(namespace: str, pod: str, script: str, env_map: dict[str, str]) -> tuple[dict[str, Any], str]:
    env_bits = [f"{key}={value}" for key, value in sorted(env_map.items())]
    proc = run(
        ["kubectl", "exec", "-n", namespace, pod, "--", "env", *env_bits, "python", "-c", script],
        timeout=240,
        check=False,
    )
    if proc.returncode != 0:
        return {}, proc.stderr.strip() or proc.stdout.strip()
    text = proc.stdout.strip()
    if not text:
        return {}, ""
    try:
        return json.loads(text), ""
    except json.JSONDecodeError as exc:
        return {}, f"json_decode_error:{exc}"


def select_running_pod(namespace: str, app: str) -> str:
    payload = json.loads(
        run(["kubectl", "get", "pods", "-n", namespace, "-l", f"app={app}", "-o", "json"], timeout=180).stdout
    )
    items = payload.get("items") or []
    for item in items:
        status = item.get("status") or {}
        phase = str(status.get("phase") or "").strip()
        if phase != "Running":
            continue
        conditions = status.get("conditions") or []
        ready = any(
            str(cond.get("type") or "").strip() == "Ready" and str(cond.get("status") or "").strip() == "True"
            for cond in conditions
        )
        if ready:
            name = str(((item.get("metadata") or {}).get("name")) or "").strip()
            if name:
                return name
    raise RuntimeError(f"PHASE6.BUNDLE.POD_UNAVAILABLE:{namespace}:{app}")


REMOTE_DLA_SCRIPT = r"""
import json
from pathlib import Path

from fraud_detection.decision_log_audit.worker import load_worker_config
from fraud_detection.decision_log_audit.storage import DecisionLogAuditIntakeStore

profile_path = Path(__import__("os").environ["FP_PROFILE_PATH"])
platform_run_id = str(__import__("os").environ["PHASE6_PLATFORM_RUN_ID"])
scenario_run_id = str(__import__("os").environ["PHASE6_SCENARIO_RUN_ID"])
limit = max(1, int(__import__("os").environ.get("PHASE6_LIMIT", "5000")))

cfg = load_worker_config(profile_path)
store = DecisionLogAuditIntakeStore(locator=cfg.index_locator, stream_id=cfg.stream_id)
governance = store.governance_stamp_summary(
    platform_run_id=platform_run_id,
    scenario_run_id=scenario_run_id,
    limit=limit,
)
quarantine = store.quarantine_reason_counts(
    platform_run_id=platform_run_id,
    scenario_run_id=scenario_run_id,
    limit=min(100, limit),
)
attempts = store.recent_attempts(
    platform_run_id=platform_run_id,
    scenario_run_id=scenario_run_id,
    limit=min(50, limit),
)
print(json.dumps({
    "platform_run_id": platform_run_id,
    "scenario_run_id": scenario_run_id,
    "index_locator": cfg.index_locator,
    "stream_id": cfg.stream_id,
    "governance": governance,
    "quarantine": quarantine,
    "recent_attempts": attempts,
}))
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Probe live DLA bundle attribution for Phase 6.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    ap.add_argument("--execution-id", required=True)
    ap.add_argument("--platform-run-id", required=True)
    ap.add_argument("--scenario-run-id", required=True)
    ap.add_argument("--namespace", default="fraud-platform-rtdl")
    ap.add_argument("--profile-path", default="/runtime-profile/dev_full.yaml")
    ap.add_argument("--artifact-prefix", default="phase6_candidate")
    ap.add_argument("--expected-bundle-id", required=True)
    ap.add_argument("--expected-bundle-version", required=True)
    ap.add_argument("--expected-policy-id", default="df.registry_resolution.v0")
    ap.add_argument("--expected-policy-revision", required=True)
    ap.add_argument("--poll-timeout-seconds", type=int, default=180)
    ap.add_argument("--probe-interval-seconds", type=int, default=10)
    ap.add_argument("--limit", type=int, default=5000)
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.execution_id
    summary_path = root / f"{str(args.artifact_prefix).strip()}_bundle_probe.json"

    expected_bundle = f"bundle://{str(args.expected_bundle_id).strip()}@{str(args.expected_bundle_version).strip()}"
    expected_policy = f"policy://{str(args.expected_policy_id).strip()}@{str(args.expected_policy_revision).strip()}"

    blockers: list[str] = []
    notes: list[str] = []
    last_payload: dict[str, Any] = {}
    probe_error = ""
    pod_name = select_running_pod(str(args.namespace).strip(), "fp-pr3-dla")
    deadline = time.time() + max(1, int(args.poll_timeout_seconds))
    attempts = 0

    while True:
        attempts += 1
        last_payload, probe_error = exec_json(
            str(args.namespace).strip(),
            pod_name,
            REMOTE_DLA_SCRIPT,
            {
                "FP_PROFILE_PATH": str(args.profile_path).strip(),
                "PHASE6_PLATFORM_RUN_ID": str(args.platform_run_id).strip(),
                "PHASE6_SCENARIO_RUN_ID": str(args.scenario_run_id).strip(),
                "PHASE6_LIMIT": str(max(1, int(args.limit))),
            },
        )
        if not probe_error:
            governance = dict(last_payload.get("governance") or {})
            bundle_refs = [str(item).strip() for item in (governance.get("bundle_refs") or []) if str(item).strip()]
            policy_refs = [str(item).strip() for item in (governance.get("policy_refs") or []) if str(item).strip()]
            if bundle_refs or policy_refs:
                break
        if time.time() >= deadline:
            break
        time.sleep(max(1, int(args.probe_interval_seconds)))

    if probe_error:
        blockers.append(f"PHASE6.B31_PROBE_FAILED:{probe_error}")

    governance = dict(last_payload.get("governance") or {})
    bundle_refs = sorted(str(item).strip() for item in (governance.get("bundle_refs") or []) if str(item).strip())
    policy_refs = sorted(str(item).strip() for item in (governance.get("policy_refs") or []) if str(item).strip())
    execution_profile_refs = sorted(
        str(item).strip() for item in (governance.get("execution_profile_refs") or []) if str(item).strip()
    )
    run_config_digests = sorted(
        str(item).strip() for item in (governance.get("run_config_digests") or []) if str(item).strip()
    )

    if not bundle_refs:
        blockers.append("PHASE6.B32_BUNDLE_REFS_UNREADABLE")
    elif bundle_refs != [expected_bundle]:
        blockers.append(f"PHASE6.B33_BUNDLE_REF_DRIFT:{'|'.join(bundle_refs)}")
    else:
        notes.append("DLA governance stamps show one bounded bundle identity for this scenario and it matches the expected active runtime bundle.")

    if not policy_refs:
        blockers.append("PHASE6.B34_POLICY_REFS_UNREADABLE")
    elif policy_refs != [expected_policy]:
        blockers.append(f"PHASE6.B35_POLICY_REF_DRIFT:{'|'.join(policy_refs)}")

    if not execution_profile_refs:
        blockers.append("PHASE6.B36_EXECUTION_PROFILE_REFS_UNREADABLE")
    if not run_config_digests:
        blockers.append("PHASE6.B37_RUN_CONFIG_DIGEST_UNREADABLE")

    quarantine = dict(last_payload.get("quarantine") or {})
    if quarantine:
        blockers.append(f"PHASE6.B38_DLA_QUARANTINE_PRESENT:{json.dumps(quarantine, sort_keys=True)}")

    summary = {
        "phase": "PHASE6",
        "generated_at_utc": now_utc(),
        "execution_id": args.execution_id,
        "platform_run_id": str(args.platform_run_id).strip(),
        "scenario_run_id": str(args.scenario_run_id).strip(),
        "namespace": str(args.namespace).strip(),
        "pod_name": pod_name,
        "probe_attempts": attempts,
        "expected_bundle_ref": expected_bundle,
        "expected_policy_ref": expected_policy,
        "governance": governance,
        "quarantine": quarantine,
        "recent_attempts": list(last_payload.get("recent_attempts") or []),
        "execution_profile_refs": execution_profile_refs,
        "run_config_digests": run_config_digests,
        "overall_pass": len(blockers) == 0,
        "blocker_ids": blockers,
        "notes": notes,
    }
    dump_json(summary_path, summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
