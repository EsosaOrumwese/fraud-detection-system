#!/usr/bin/env python3
"""Application-level warm gate for PR3 runtime before burst injection."""

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


def get_json(cmd: list[str], *, timeout: int = 180) -> dict[str, Any]:
    proc = run(cmd, timeout=timeout, check=True)
    text = proc.stdout.strip()
    return json.loads(text) if text else {}


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


DF_WARM_SCRIPT = r"""
import json
from pathlib import Path

from fraud_detection.decision_fabric.registry import RegistryScopeKey, RegistrySnapshot
from fraud_detection.decision_fabric.worker import load_worker_config
from fraud_detection.event_bus.kafka import build_kafka_reader

profile_path = Path(__import__("os").environ["FP_PROFILE_PATH"])
cfg = load_worker_config(profile_path)
snapshot = RegistrySnapshot.load(cfg.registry_snapshot_ref)
reader = build_kafka_reader(client_id="pr3-df-warm-gate")
topic = "fp.bus.traffic.fraud.v1"
partitions = reader.list_partitions(topic)
required = [
    RegistryScopeKey(environment="dev_full", mode="fraud", bundle_slot="primary").canonical_key(),
    RegistryScopeKey(environment="dev_full", mode="baseline", bundle_slot="primary").canonical_key(),
]
present = sorted(snapshot.records_by_scope.keys())
print(json.dumps({
    "required_platform_run_id": cfg.required_platform_run_id,
    "event_bus_start_position": cfg.event_bus_start_position,
    "registry_snapshot_ref": str(cfg.registry_snapshot_ref),
    "snapshot_id": snapshot.snapshot_id,
    "snapshot_digest": snapshot.snapshot_digest,
    "required_scopes_present": all(scope in snapshot.records_by_scope for scope in required),
    "required_scopes": required,
    "present_scopes": present,
    "kafka_topic": topic,
    "kafka_partitions": partitions,
}))
"""

CSFB_WARM_SCRIPT = r"""
import json
from pathlib import Path

from fraud_detection.context_store_flow_binding.intake import CsfbInletPolicy
from fraud_detection.context_store_flow_binding.observability import CsfbObservabilityReporter
from fraud_detection.event_bus.kafka import build_kafka_reader

profile_path = Path(__import__("os").environ["FP_PROFILE_PATH"])
policy = CsfbInletPolicy.load(profile_path)
reader = build_kafka_reader(client_id="pr3-csfb-warm-gate")
topic_partitions = {topic: reader.list_partitions(topic) for topic in policy.context_topics}
reporter = CsfbObservabilityReporter.build(locator=policy.projection_db_dsn, stream_id=policy.stream_id)
snapshot = reporter.collect(platform_run_id=policy.required_platform_run_id)
print(json.dumps({
    "required_platform_run_id": policy.required_platform_run_id,
    "event_bus_start_position": policy.event_bus_start_position,
    "projection_db_dsn": policy.projection_db_dsn,
    "stream_id": policy.stream_id,
    "context_topics": list(policy.context_topics),
    "topic_partitions": topic_partitions,
    "metrics": snapshot.get("metrics", {}),
    "checkpoints": snapshot.get("checkpoints", {}),
    "health_state": snapshot.get("health_state"),
    "health_reasons": snapshot.get("health_reasons", []),
}))
"""


def pod_status(namespace: str, app: str) -> dict[str, Any]:
    pods = get_json(["kubectl", "get", "pods", "-n", namespace, "-l", f"app={app}", "-o", "json"], timeout=120)
    items = list(pods.get("items", []) or [])
    if not items:
        return {"app": app, "pod_missing": True}
    pod = items[0]
    statuses = list(pod.get("status", {}).get("containerStatuses", []) or [])
    return {
        "app": app,
        "pod_name": str(pod.get("metadata", {}).get("name", "")).strip(),
        "phase": str(pod.get("status", {}).get("phase", "")).strip(),
        "ready": all(bool(row.get("ready")) for row in statuses) if statuses else False,
        "restart_count": int(sum(int(row.get("restartCount", 0) or 0) for row in statuses)),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Warm-gate PR3 runtime before injection.")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr3-execution-id", required=True)
    ap.add_argument("--state-id", default="S2")
    ap.add_argument("--namespace", default="fraud-platform-rtdl")
    ap.add_argument("--profile-path", default="/runtime-profile/dev_full.yaml")
    ap.add_argument("--platform-run-id", required=True)
    ap.add_argument("--settle-seconds", type=int, default=30)
    ap.add_argument("--generated-by", default="codex-gpt5")
    ap.add_argument("--version", default="1.0.0")
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.pr3_execution_id
    root.mkdir(parents=True, exist_ok=True)
    out_path = root / f"g3a_{str(args.state_id).strip().lower()}_runtime_warm_gate.json"

    blockers: list[str] = []
    components = [
        "fp-pr3-csfb",
        "fp-pr3-ieg",
        "fp-pr3-ofp",
        "fp-pr3-df",
        "fp-pr3-al",
        "fp-pr3-dla",
        "fp-pr3-archive-writer",
    ]
    pre_status = [pod_status(args.namespace, app) for app in components]
    for row in pre_status:
        if row.get("pod_missing"):
            blockers.append(f"PR3.{args.state_id}.WARM.B01_POD_MISSING:{row['app']}")
            continue
        if row.get("phase") != "Running" or not bool(row.get("ready")):
            blockers.append(f"PR3.{args.state_id}.WARM.B02_POD_NOT_READY:{row['app']}")

    df_probe, df_probe_error = ({}, "")
    csfb_probe, csfb_probe_error = ({}, "")
    if not blockers:
        csfb_status = next(row for row in pre_status if row.get("app") == "fp-pr3-csfb")
        csfb_probe, csfb_probe_error = exec_json(
            args.namespace,
            str(csfb_status["pod_name"]),
            CSFB_WARM_SCRIPT,
            {"FP_PROFILE_PATH": args.profile_path},
        )
        if csfb_probe_error:
            blockers.append(f"PR3.{args.state_id}.WARM.B03_CSFB_PROBE_FAILED:{csfb_probe_error}")
        else:
            if str(csfb_probe.get("required_platform_run_id") or "").strip() != args.platform_run_id:
                blockers.append(
                    f"PR3.{args.state_id}.WARM.B04_CSFB_PLATFORM_RUN_SCOPE_MISMATCH:"
                    f"{csfb_probe.get('required_platform_run_id')}"
                )
            topic_partitions = dict(csfb_probe.get("topic_partitions") or {})
            for topic in csfb_probe.get("context_topics") or []:
                if not list(topic_partitions.get(topic) or []):
                    blockers.append(f"PR3.{args.state_id}.WARM.B05_CSFB_TOPIC_METADATA_UNREADABLE:{topic}")

        df_status = next(row for row in pre_status if row.get("app") == "fp-pr3-df")
        df_probe, df_probe_error = exec_json(
            args.namespace,
            str(df_status["pod_name"]),
            DF_WARM_SCRIPT,
            {"FP_PROFILE_PATH": args.profile_path},
        )
        if df_probe_error:
            blockers.append(f"PR3.{args.state_id}.WARM.B06_DF_PROBE_FAILED:{df_probe_error}")
        else:
            if str(df_probe.get("required_platform_run_id") or "").strip() != args.platform_run_id:
                blockers.append(
                    f"PR3.{args.state_id}.WARM.B07_PLATFORM_RUN_SCOPE_MISMATCH:"
                    f"{df_probe.get('required_platform_run_id')}"
                )
            if not bool(df_probe.get("required_scopes_present")):
                blockers.append(f"PR3.{args.state_id}.WARM.B08_DF_SCOPE_BRIDGE_MISSING")
            if not list(df_probe.get("kafka_partitions") or []):
                blockers.append(f"PR3.{args.state_id}.WARM.B09_DF_KAFKA_METADATA_UNREADABLE")

    if not blockers and args.settle_seconds > 0:
        time.sleep(args.settle_seconds)

    post_status = [pod_status(args.namespace, app) for app in components]
    if not blockers:
        for before, after in zip(pre_status, post_status, strict=False):
            if after.get("pod_missing"):
                blockers.append(f"PR3.{args.state_id}.WARM.B10_POD_DISAPPEARED:{after['app']}")
                continue
            if after.get("phase") != "Running" or not bool(after.get("ready")):
                blockers.append(f"PR3.{args.state_id}.WARM.B11_POD_NOT_STABLE:{after['app']}")
            if int(after.get("restart_count", 0) or 0) > int(before.get("restart_count", 0) or 0):
                blockers.append(f"PR3.{args.state_id}.WARM.B12_RESTART_DURING_SETTLE:{after['app']}")

    payload = {
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "generated_by": args.generated_by,
        "version": args.version,
        "execution_id": args.pr3_execution_id,
        "platform_run_id": args.platform_run_id,
        "namespace": args.namespace,
        "profile_path": args.profile_path,
        "settle_seconds": args.settle_seconds,
        "pre_status": pre_status,
        "csfb_probe": csfb_probe,
        "csfb_probe_error": csfb_probe_error,
        "df_probe": df_probe,
        "df_probe_error": df_probe_error,
        "post_status": post_status,
        "overall_pass": len(blockers) == 0,
        "blocker_ids": sorted(set(blockers)),
    }
    dump_json(out_path, payload)
    print(json.dumps(payload, indent=2))
    if blockers:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
